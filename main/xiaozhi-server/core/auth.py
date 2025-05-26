from config.logger import setup_logging
import requests

TAG = __name__
logger = setup_logging()


class DeviceManager:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
            "accept": "*/*"
        }
    
    def _handle_response(self, response):
        """统一处理响应"""
        try:
            response.raise_for_status()
            result = response.json()
            
            if not result.get('success'):
                print(f"业务错误 [{result.get('getcode')}]: {result.get('getmsg')}")
                return None
                
            return result.get('data')
            
        except requests.exceptions.HTTPError as e:
            print(f"HTTP错误 {response.status_code}: {str(e)}")
            if response.status_code == 401:
                print("认证失败：可能原因如下")
                print("1. Token已过期（当前有效期至2030年）")
                print("2. 缺少设备管理权限")
                print(f"追踪ID: {result.get('traceId', '无')}")
            else:
                print(f"HTTP错误 {response.status_code}: {str(e)}")
            return None

    def save_device(self, device_info):
        """保存设备信息（全量字段）"""
        url = f"{self.base_url}/device/save"

        return self._handle_response(requests.post(
            url, 
            headers=self.headers,
            json=device_info,
            timeout=15
        ))


    # 保留已有查询方法
    def update_device_status(self, device_id, status):
        """获取设备详情"""
        url = f"{self.base_url}/device/statusUpdate"
        return self._handle_response(
            requests.post(url, headers=self.headers, json={"deviceId": device_id,"onlineStatus": status})
        )
    
    def update_device_battery_level(self, device_id, battery_level):
        """获取设备详情"""
        url = f"{self.base_url}/device/statusUpdate"
        return self._handle_response(
            requests.post(url, headers=self.headers, json={"deviceId": device_id,"voltagePercentage": battery_level})
        )
    
    def get_device_detail(self, device_id):
        """获取设备详情"""
        url = f"{self.base_url}/device/detail"
        return self._handle_response(
            requests.post(url, headers=self.headers, json={"deviceId": device_id})
        )

class AuthenticationError(Exception):
    """认证异常"""
    pass


class AuthMiddleware:
    def __init__(self, config):
        self.config = config
        self.auth_config = config["server"].get("auth", {})
        self.device_id = ''
        # # 构建token查找表
        # self.tokens = {
        #     item["token"]: item["name"]
        #     for item in self.auth_config.get("tokens", [])
        # }
        # 设备白名单
        self.allowed_devices = set(
            self.auth_config.get("allowed_devices", [])
        )
        self.TOKEN = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiItMSIsImlhdCI6MTc0NzEyOTAyMywiZXhwIjoxOTA0ODA5MDIzfQ.9qLXdSVifTTrjLo6ph0cp8S7nAECVzzdvQFM-_8vdd8"  # 生产环境应从安全存储读取
        self.manager = DeviceManager("http://api.landoubao.com:8002/api", self.TOKEN)
        self.device_bind_status = False

    async def authenticate(self, headers):
        """验证连接请求"""
        # 检查是否启用认证
        if not self.auth_config.get("enabled", False):
            return True

        # 获取设备id
        self.device_id = headers.get("client-id", "")
        logger.bind(tag=TAG).warning(f"Authentication successful - Device: {self.device_id}")

        if self.allowed_devices and self.device_id in self.allowed_devices:
            # logger.bind(tag=TAG).warning(f"白名单设备 - Device: {self.device_id}")
            return True
        

        # # 验证Authorization header
        # auth_header = headers.get("authorization", "")
        # if not auth_header.startswith("Bearer "):
        #     logger.bind(tag=TAG).error("Missing or invalid Authorization header")
        #     raise AuthenticationError("Missing or invalid Authorization header")

        # token = auth_header.split(" ")[1]
        # if token not in self.tokens:
        #     logger.bind(tag=TAG).error(f"Invalid token: {token}")
        #     raise AuthenticationError("Invalid token")
        
        # 查询是否绑定
        device_data = self.manager.get_device_detail(self.device_id)
        if device_data is None:
            logger.bind(tag=TAG).warning("设备未绑定") 
            # return False
            raise AuthenticationError("Invalid client-id")
        logger.bind(tag=TAG).info("设备详情获取成功：")
        logger.bind(tag=TAG).info(f"设备名称: {device_data['deviceName']}")
        logger.bind(tag=TAG).info(f"MAC地址: {device_data['macAddress']}")
        logger.bind(tag=TAG).info(f"版本号: {device_data['firmwareVersion']}")
        logger.bind(tag=TAG).info(f"在线状态: {'在线' if device_data['onlineStatus'] ==1 else '离线'}")
        logger.bind(tag=TAG).info(f"绑定状态: {'已绑定' if device_data['bindStatus'] ==1 else '未绑定'}")
        if device_data.get("bindStatus") != 1:
            logger.bind(tag=TAG).warning("设备未绑定") 
            return False
            # raise AuthenticationError("Invalid client-id")
        
        self.device_bind_status = True
        # self.device_id = device_id
        
        # self.manager.update_device_status("6842FA4D-FC12-8F6B-5A7D-C7B244E12833", 1)  # 更新设备状态为在线

        logger.bind(tag=TAG).info(f"Authentication successful - Device: {self.device_id}")
        
        return True

    def get_token_name(self, token):
        """获取token对应的设备名称"""
        return self.tokens.get(token)
    
    async def set_device_online(self):
        """设置设备在线状态"""
        if not self.device_bind_status:
            logger.bind(tag=TAG).info("设备未绑定，无法设置在线状态")
            return False
        self.manager.update_device_status(self.device_id, 1)
        logger.bind(tag=TAG).info(f"设置设备在线状态成功：{self.device_id}")
        return True
    async def set_device_offline(self):
        """设置设备离线状态"""
        if not self.device_bind_status:
            logger.bind(tag=TAG).info("设备未绑定，无法设置离线状态")
            return False
        self.manager.update_device_status(self.device_id, 0)
        logger.bind(tag=TAG).info(f"设置设备离线状态成功：{self.device_id}")
        return True
    async def update_device_battery(self, level):
        """更新设备电量"""
        if not self.device_bind_status:
            logger.bind(tag=TAG).info("设备未绑定，无法更新电量")
            return False
        self.manager.update_device_battery_level(self.device_id, level)
        logger.bind(tag=TAG).info(f"设置设备离线状态成功：{self.device_id}")
        return True
