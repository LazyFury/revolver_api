from functools import wraps
import inspect
from os import environ
from django.http import HttpRequest
from django.urls import re_path
from revolver_api.revolver_api.utils.get_request_args import  get_instance_from_args_or_kwargs
from revolver_api.revolver_api.response import ApiErrorCode, ApiJsonResponse


def valid_method_middlewares(method="GET"):
    def middleware(request:HttpRequest):
        print("valid_method_middlewares",request.method)
        if request.method == method:
            return True
        else:
            raise Exception("不支持的请求方法")
    return middleware


class Router():
    """_summary_
    """
    def __init__(self,baseUrl="api/") -> None:
        self.baseUrl = baseUrl
    
    routes = []
    routeMap = {}
    
    def route(self,url, middlewares=[],name_suffix="",
                exception_json=True,
                description=""
        ):
        """_summary_

        Args:
            url (_type_): _description_
            middlewares (list, optional): _description_. Defaults to [].
        """
        def decorator(func):
            
            @wraps(func)
            def inner(*args, **kwargs):
                request = get_instance_from_args_or_kwargs(HttpRequest, args, kwargs)
                for middleware in middlewares:
                    print("midd:",middleware.__name__)
                    try:
                        next = middleware(request)
                        if next:
                            return func(*args, **kwargs)
                    except Exception as e:
                        if environ.get("DEBUG") == "True":
                            raise e
                        if not exception_json:
                            raise e
                        return ApiJsonResponse.error(ApiErrorCode.ERROR,str(e))
                    
            # self.urls.append(path(url, inner, name=func.__name__ + name_suffix))
            file = inspect.getsourcefile(func)
            self.routeMap[url] = {
                "name": func.__name__ + name_suffix,
                "description": description,
                "file": "vscode://file/" + file + ":" + str(func.__code__.co_firstlineno),
                "func": inner,
            }
            self.routes.append({
                "url": "/" + url,
                "name": func.__name__ + name_suffix,
                "description": description,
                "file": "vscode://file/" + file + ":" + str(func.__code__.co_firstlineno),
            })
            return inner
            
        return decorator
    
    def get(self,url,middlewares=[],**kwargs):
        # TODO：合并 middlewares
        return self.route(url,middlewares=[valid_method_middlewares("GET"),*middlewares] ,name_suffix="_get",**kwargs)

    def post(self,url,middlewares=[],**kwargs):
        return self.route(url,middlewares=[valid_method_middlewares("POST")] + middlewares,name_suffix="_post",**kwargs)
    
    def put(self,url,middlewares=[],**kwargs):
        return self.route(url,middlewares=[valid_method_middlewares("PUT")] + middlewares,name_suffix="_put",**kwargs)
    
    def delete(self,url,middlewares=[],**kwargs):
        return self.route(url,middlewares=[valid_method_middlewares("DELETE")] + middlewares,name_suffix="_delete",**kwargs)
    
    def resource(self,baseUrl,middlewares=[],**kwargs):
        def wrapper(obj):
            o =  obj()
            if hasattr(o,"register"):
                print("register",baseUrl,middlewares)
                o.register(self,baseUrl,middlewares=middlewares,**kwargs)
        return wrapper
    
    @property
    def urls(self):
        return [
            # re_path(r"^api/(.*)$", Router.handler, name="api")
            re_path(r"^" + self.baseUrl + "(.*)$", Router.handler, name="api")
        ]
    
    
    @staticmethod
    def handler(request: HttpRequest,path: str):
        func = Router.routeMap.get(path)
        if func is None:
            return ApiJsonResponse.error(ApiErrorCode.ERROR,"未找到对应的路由")
        if path in ['users.detail1']:
            return ApiJsonResponse.error(ApiErrorCode.AUTH_ERROR,"未登录")
        return func["func"](request)
        
        
    

