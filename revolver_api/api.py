import datetime
from functools import wraps
import json
from os import environ
import os
import re
from typing import Any, Iterable
from django.http import HttpRequest, HttpResponse, JsonResponse
from .model import SerializerModel
from .utils.get_request_args import get_instance_from_args_or_kwargs
from .response import ApiErrorCode, ApiJsonResponse
from .route import Router
from django.db import models
from django.contrib.auth.models import AbstractUser

def errorHandler(json=True):
    """api 错误处理

    Args:
        json (bool, optional): _description_. Defaults to True.
    """
    def wrapper(func):
        # print("errorHandler",func.__name__)
        
        @wraps(func)
        def err_inner(*args, **kwargs):
            # print("errorHandler inner")
            try:
                print("working fine....")
                return func(*args, **kwargs)
            except Exception as e:
                if json is False:
                    raise e
                return ApiJsonResponse({} if not hasattr(e,'data') else getattr(e,'data'), code=ApiErrorCode.ERROR,message=str(e) or "error")
        return err_inner
    return wrapper



class ApiException(Exception):
    code = 400
    message = "api exception"


class Rule:
    name: str = ""
    required: bool = False
    type: str = "string"
    max_length: int = 0
    min_length: int = 0
    max: int = 0
    min: int = 0
    choices: Iterable = []
    default: str = ""
    message: str = ""
    validator = bool = lambda *args, **kwargs: True

    def __init__(self,name, message="", **kwargs):
        self.name = name
        self.message = message
        for key in kwargs:
            setattr(self, key, kwargs[key])
            
    def is_required(self):
        self.required = True
        return self
    def string(self):
        self.type = "string"
        return self
    def number(self):
        self.type = "number"
        return self
    def set_choices(self,choices):
        self.choices = choices
        return self
    def set_min(self,min):
        self.min = min
        return self
    def set_max(self,max):
        self.max = max
        return self
    def set_message(self,message):
        self.message = message
        return self
    

def validator(rules: Iterable[Rule]=[],method="get"):
    def wrapper(func):
        @wraps(func)
        def inner(*args,**kwargs):
            try:
                req = get_instance_from_args_or_kwargs(HttpRequest,args,kwargs)
            except Exception as e:
                return ApiJsonResponse.error(ApiErrorCode.ERROR,e.__str__())
            params = {}
            if method.lower() == 'get':
                params = req.GET.dict()
            else:
                params = req.POST.dict()
                if req.headers.get("Content-Type") == "application/json":
                    try:
                        params = json.loads(req.body)
                    except Exception as e:
                        return ApiJsonResponse.error(ApiErrorCode.ERROR,"json 解析错误")
            
            print("!!! params:",params)
            for rule in rules:
                value = params.get(rule.name)
                if rule.required and value is None or value == "":
                    return ApiJsonResponse(None,code=ApiErrorCode.ERROR,message=rule.message)
            
            print("validator",func.__name__)
            req.valid_data = params
            return func(*args,**kwargs)
        return inner
    return wrapper
class Api:
    """# 生成API

    Returns:
        _type_: _description_
    """

    model: SerializerModel

    rules: Iterable[Rule] = []


    public_view = False
    user_field = "user"
    
    @property
    def shoud_find_by_user(self):
        """ 是否应该根据用户 id 查询

        Returns:
            _type_: _description_
        """
        foreign_leys = [f for f in self.model._meta.get_fields() if f.is_relation]
        for f in foreign_leys:
            if isinstance(f.related_model(),AbstractUser):
                return True
        return False
    
    def is_supperuser(self,request: HttpRequest):
        """是否是后台管理员

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        return request.user and request.user.is_superuser
    
    
    def find_by_user_query(self,query: models.QuerySet,user:AbstractUser)->models.QuerySet:
        """查找用户外键的方法

        Args:
            query (models.QuerySet): _description_
            user (_type_): _description_

        Returns:
            _type_: _description_
        """
        data = {
            self.user_field:user
        }
        return query.filter(**data)
    
    def find_by_user(self,query: models.QuerySet,request: HttpRequest,view_only=False)->models.QuerySet:
        """判断是否应该根据用户 id 查询

        Args:
            query (models.QuerySet): _description_
            request (HttpRequest): _description_
            view_only (bool, optional): _description_. Defaults to False.

        Returns:
            _type_: _description_
        """
        if self.is_supperuser(request):
            return query
        if view_only and self.public_view:
            return query
        if self.shoud_find_by_user:
            print("根据用户查询",query)
            return self.find_by_user_query(query=query,user=request.user)
        else:
            print("不公开数据，且当前用户也没有权限",query)
            return query.filter(pk=-1)
        
    def auto_save_with_user(self,request: HttpRequest, obj: models.Model):
        """自动保存用户

        Args:
            request (HttpRequest): _description_
            obj (models.Model): _description_
        """
        if self.shoud_find_by_user:
            print("has user field",hasattr(obj,"user"))
            print("user",request.user)
            # superuser 在后台手动选择用户时，不会自动保存用户
            if self.is_supperuser(request):
                if (hasattr(obj,"user") is False or getattr(obj,"user") is None):
                    setattr(obj,"user",request.user)
            else:
                setattr(obj,"user",request.user)
        obj.save()
    
    class Validator:
        is_valid = True
        errors = {}

        @property
        def tips(self):
            for key in self.errors:
                return self.errors[key]

        def add_error(self, key, value):
            self.is_valid = False
            self.errors[key] = value

    def validate(self, request: HttpRequest, data=None,**kwargs):
        """### 提交数据验证

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        # print(self.model, "validate")
        validator = self.Validator()
        for rule in self.rules:
            value = data or request.POST.get(rule.name)
            if rule.required is True and (value is None or value == ""):
                validator.add_error(
                    rule.name, rule.message if rule.message else "required"
                )
                continue
            if rule.type == "string":
                value = value if value else ""
                if rule.max_length > 0 and len(value) > rule.max_length:
                    validator.add_error(rule.name, f"max_length {rule.max_length}")
                    continue
                if rule.min_length > 0 and len(value) < rule.min_length:
                    validator.add_error(rule.name, f"min_length {rule.min_length}")
                    continue
            if rule.type == "number":
                value = int(value if value else 0)
                if rule.max > 0 and value > rule.max:
                    validator.add_error(rule.name, f"max {rule.max}")
                    continue
                if rule.min > 0 and value < rule.min:
                    validator.add_error(rule.name, f"min {rule.min}")
                    continue
            if rule.type == "choices":
                if value not in rule.choices:
                    validator.add_error(rule.name, f"choices is not in {rule.choices}")
                    continue
            if rule.validator(value) is False:
                validator.add_error(
                    rule.name, rule.message if rule.message else "自定义验证错误"
                )
                continue
        return validator

    def create(self, request: HttpRequest, **kwargs):
        """### 创建数据

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        if request.method != "POST":
            return JsonResponse({"error": "only support POST"})
        
        if not self.is_supperuser(request=request):
            if self.shoud_find_by_user and (request.user is None or request.user.is_anonymous):
                return ApiJsonResponse.error(ApiErrorCode.ERROR,"没有权限")
        
        print(self.model, "createApi")
        try:
            data = json.loads(request.body)
        except Exception as e:
            return ApiJsonResponse.error(ApiErrorCode.ERROR,e.__str__())
        validator = self.validate(request,data=data, **kwargs)
        if validator.is_valid is False:
            return ApiJsonResponse.error(
                data={
                    "errors": validator.errors,
                },
                message= validator.tips if validator.tips else "",
            )
        try:
            dict = data
            if id in dict:
                del dict["id"]
            
            obj = self.model.objects.create(**dict)
            self.auto_save_with_user(request, obj)
        except Exception as e:
            return ApiJsonResponse.error(ApiErrorCode.ERROR,e.__str__())
        return JsonResponse(
            {
                "status": "success",
                "code": 200,
                "data": obj.to_json(),
            }
        )

    def update(self, request: HttpRequest, **kwargs):
        """### 更新数据

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        try:
            data = json.loads(request.body)
        except Exception as e:
            return ApiJsonResponse.error(data={},message=e.__str__() or "json 解析错误")
        validator = self.validate(request,data=data, **kwargs)
        if validator.is_valid is False:
            return ApiJsonResponse.error(
                data={
                    "errors": validator.errors,
                },
                message= validator.tips if validator.tips else "",
            )
        id = data.get("id")
        if id is None or id == "":
            return ApiJsonResponse.error(ApiErrorCode.ERROR,"id 不能为空")
        query = self.find_by_user(query=self.model.objects.filter(pk=id),request=request)
        print("update",query.count())
        # .first()
        obj = query.first()
        print("update",obj)
        
        if obj is None:
            return ApiJsonResponse.error(ApiErrorCode.NOT_FOUND,"无法更新/没有权限")
        for key in obj.fillable():
            setattr(obj, key, data.get(key))
        try:
            obj.save()
        except Exception as e:
            return ApiJsonResponse.error(ApiErrorCode.ERROR,e.__str__())
        return ApiJsonResponse.success(obj.to_json())
        
    def defaultQuery(self,request: HttpRequest):
        """### 默认查询

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        
        model_fields = self.model._meta.get_fields()
        valid_fields = {}
        input_fields = request.GET.dict()
        
        # 忽略不在模型中的字段，前端在查询时可能会传入一些不在模型中的字段，这些字段应该被忽略
        for field in model_fields:
            for key in input_fields:
                if not re.match(f'{field.name}(\w+)?$',key):
                    continue
                if input_fields[key] == "" or input_fields[key] is None:
                    continue
                else:
                    valid_fields[key] = input_fields[key]
                    # trim 
                    if isinstance(input_fields[key],str):
                        valid_fields[key] = input_fields[key].strip()
        
        query = self.model.objects.all().filter(**valid_fields).order_by("-created_at")
        
        order_by_set = request.GET.get("order_by")
        if order_by_set is not None and order_by_set != "":
            for order_by in order_by_set.split(","):
                if order_by.endswith("_desc"):
                    query = query.order_by("-" + order_by.replace("_desc",""))
                if order_by.endswith("_asc"):
                    query = query.order_by(order_by.replace("_asc",""))
        
        return self.find_by_user(query,request=request,view_only=True)
        
    def list(self, request: HttpRequest, **kwargs):
        if request.method != "GET":
            return JsonResponse({"error": "only support GET"})
        # print(self.model, "pageApi")
        if self.validate(request, **kwargs) is False:
            return JsonResponse({"error": "validate error"})
        page, size = request.GET.get("page", 1), request.GET.get("size", 10)
        page = int(page)
        size = int(size)
        objs = self.defaultQuery(request=request)
        count = objs.count()
        objs = objs[
            (page - 1) * size : (page) * size
        ]
        arr = []
        for obj in objs:
            if hasattr(obj, "to_json"):
                arr.append(obj.to_json())
            else:
                arr.append(obj)
        return ApiJsonResponse(
            {
                "pageable": {
                    "page": page,
                    "size": size,
                    "total": count,
                    "totalPage": count // size + 1,
                },
                "list": arr,
            },
            message="获取成功",
        )
    
        
    
    @staticmethod
    def get_db_fields(model:SerializerModel):
        return model.objects.first().to_json().keys()
    
    @staticmethod
    def export_csv_override(query:models.QuerySet,request:HttpRequest):
        """导出csv

        Args:
            query (models.QuerySet): _description_
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        from xlwt import Workbook,easyxf,add_palette_colour
        work = Workbook()
        add_palette_colour("custom_colour", 0x21)
        work.set_colour_RGB(0x21, 235, 235, 235)
        
        header_style = easyxf('pattern: pattern solid, fore_colour custom_colour;\
            borders: left thin, right thin, top thin, bottom thin;\
            font: bold 1,height 240;')
        
        
        model:SerializerModel = query.model
        name = request.GET.get("name") or model.__name__.lower() + "_export_" + str(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"))
        file_name = name + ".xls"
        file_path = ("tmp")
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path))
        file_path = os.path.join(file_path,file_name)
        print("export_csv",file_path)
        try:
            sheet = work.add_sheet("sheet1")
            data = []
            for obj in query:
                data.append(obj)
            if len(data) == 0:
                return ApiJsonResponse.error(ApiErrorCode.NOT_FOUND,"没有找到记录")
            fields = list(Api.get_db_fields(model))
            
            sorted_fields = sorted(fields,key=lambda k:model.xls_sort_key(k) )
            
            for i,field in enumerate(sorted_fields):
                obj:SerializerModel = data[0]
                remark = model.get_xls_key_remark(obj,field)
                width = len(remark) * 400
                width = max(width,3600)
                sheet.col(i).width = width
                # sheet.write(0,i,remark,header_style)
                sheet.write(0,i,remark,header_style)
            for i,obj in enumerate(data):
                row = obj.to_json()
                row_style = easyxf('font: height 320;')
                sheet.row(i+1).set_style(row_style)
                for j,field in enumerate(sorted_fields):
                    val = obj.to_xls_format(row,field)
                    sheet.write(i+1,j,val)
            work.save(file_path)
        except Exception as e:
            return ApiJsonResponse.error(ApiErrorCode.ERROR,e.__str__())
        with open(file_path,"rb") as f:
            response = HttpResponse(f,content_type="application/vnd.ms-excel")
            response['Content-Disposition'] = 'attachment; filename="export.xls"'
            return response
        
    def export_csv(self,request: HttpRequest):
        query = self.defaultQuery(request)
        return self.export_csv_override(query,request)

    @validator([
        Rule(name="id", required=True, message="id不能为空"),
    ])
    def detail(self, request: HttpRequest):
        if request.method != "GET":
            return JsonResponse({"error": "only support GET"})
        id = request.GET.get("id")
        # print(self.model, "get_one",id)
        try:
            obj = self.find_by_user(self.model.objects.filter(pk=id),request=request).first()
        except Exception as e:
            if environ.get("DEBUG") == "True":
                raise e
            return ApiJsonResponse.error(ApiErrorCode.NOT_FOUND,"没有 id 为 "+ id +" 的找到记录")
        return JsonResponse(
            {
                "status": "success",
                "code": 200,
                "data": obj.to_json(),
            }
        )

    @validator([
        Rule(name="ids",message="ids 必传！")
    ])
    def delete(self, request: HttpRequest):
        data = json.loads(request.body)
        ids = data.get("ids",[])
        if request.method != "DELETE":
            raise Exception("not support http method")
        try:
            for id in ids:
                obj = self.find_by_user(self.model.objects.filter(pk=id),request=request).first()
                if obj is not None:
                    obj.delete()
            return ApiJsonResponse.success()
        except Exception as e:
            return ApiJsonResponse.error(message=e.__str__())

    @property
    def urls(self):
        return self.get_urls(), "api", self.model.__name__.lower()
    
    @property
    def routeName(self):
        return self.model.__name__.lower()

    def __init__(self, *args: Any, **kwds: Any) -> Any:
        pass
    
    def register(self,router:Router,baseUrl="api",middlewares=[]):
        router.get(baseUrl,middlewares=middlewares)(self.list)
        router.post(baseUrl + '.create',middlewares=middlewares)(self.create)
        router.get(baseUrl + '.detail',middlewares=middlewares)(self.detail)
        router.delete(baseUrl + '.delete',middlewares=middlewares)(self.delete)
        router.put(baseUrl + '.update',middlewares=middlewares)(self.update)
        router.get(baseUrl + '.export',middlewares=middlewares)(self.export_csv)
    
