import enum
from django.http import JsonResponse



            
            
class ApiErrorCode(enum.Enum):
    SUCCESS = 200, "成功"
    ERROR = 400, "失败"
    AUTH_ERROR = 401, "认证失败"
    AUTH_EXPIRED = 402, "认证过期"
    NOT_FOUND = 404, "资源不存在"
    
    USER_NOT_EXIST = 1001, "用户不存在"
    USER_EXIST = 1002, "用户已存在"
    USER_PASSWORD_ERROR = 1003, "密码错误"
    USER_PASSWORD_NOT_MATCH = 1004, "密码不匹配"
    
    USER_NOT_LOGIN = 1005, "用户未登录"
    USER_NOT_AUTH = 1006, "用户未认证"
    TOKEN_INVALID = 1007, "token无效"

class ApiJsonResponse(JsonResponse):
    def __init__(self, data, message="", code=ApiErrorCode.SUCCESS,httpCode=200, **kwargs):
        super().__init__(
            {
                "message": message or code.value[1], 
                "code": code.value[0], 
                "data": data
            },
            safe=False,
            json_dumps_params={"ensure_ascii": False, "indent": 4},
            **kwargs,
        )
        self["Access-Control-Allow-Origin"] = "*"
        self["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS, PUT, DELETE"
        self["Access-Control-Max-Age"] = "1000"
        self["Access-Control-Allow-Headers"] = "*"
        self.status_code = httpCode
        
    def error(code=ApiErrorCode.ERROR,message="错误",data=None,**kwargs):
        
        return ApiJsonResponse(data,code=code,message=message,httpCode=400,**kwargs)
    
    def success(data=None,message="成功",**kwargs):
        return ApiJsonResponse(data,code=ApiErrorCode.SUCCESS,message=message,httpCode=200,**kwargs)

