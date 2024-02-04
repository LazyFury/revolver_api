from calendar import c
import datetime
from functools import wraps
import json
from os import environ
import re
from typing import Any, Iterable
from django.http import HttpRequest, HttpResponse, JsonResponse
from .model import SerializerModel
from .utils.get_request_args import get_instance_from_args_or_kwargs
from .response import ApiErrorCode, ApiJsonResponse
from .route import Router
from core import config
from django.db import models

def errorHandler(json=True):
    """api 错误处理

    Args:
        json (bool, optional): _description_. Defaults to True.
    """
    def wrapper(func):
        print("errorHandler",func.__name__)
        
        @wraps(func)
        def err_inner(*args, **kwargs):
            print("errorHandler inner")
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

    # filter only self if not superuser
    is_supperuser = True
    public_view = False
    
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

    def validate(self, request: HttpRequest, **kwargs):
        """### 提交数据验证

        Args:
            request (HttpRequest): _description_

        Returns:
            _type_: _description_
        """
        print(self.model, "validate")
        validator = self.Validator()
        for rule in self.rules:
            value = request.POST.get(rule.name)
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
        print(self.model, "createApi")
        validator = self.validate(request, **kwargs)
        if validator.is_valid is False:
            return JsonResponse(
                {
                    "code": 400,
                    "msg": "validate error",
                    "tips": validator.tips if validator.tips else "",
                    "errors": validator.errors,
                }
            )
        try:
            dict = request.POST.dict()
            del dict["id"]
            obj = self.model.objects.create(**dict)
        except Exception as e:
            return JsonResponse({"error": str(e)})
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
        if request.method != "POST":
            return JsonResponse({"error": "only support POST"})
        # print(self.model, "createApi")
        validator = self.validate(request, **kwargs)
        if validator.is_valid is False:
            return JsonResponse(
                {
                    "code": 400,
                    "msg": "validate error",
                    "tips": validator.tips if validator.tips else "",
                    "errors": validator.errors,
                }
            )
        id = request.POST.get("id")
        if id is None or id == "":
            return JsonResponse({"error": "id is required"})
        obj = self.model.objects.filter(pk=id).first()
        if obj is None:
            return JsonResponse({"error": "not found"})
        for key in request.POST.dict():
            setattr(obj, key, request.POST.dict()[key])
        try:
            obj.save()
        except Exception as e:
            return JsonResponse({"error": str(e)})
        return JsonResponse(
            {
                "status": "success",
                "code": 200,
                "msg": "update success",
                "data": obj.to_json(),
            }
        )
        
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
        
        return query
        
    def list(self, request: HttpRequest, **kwargs):
        if request.method != "GET":
            return JsonResponse({"error": "only support GET"})
        print(self.model, "pageApi")
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
        
        
        model = query.model
        name = request.GET.get("name") or model.__name__.lower() + "_export_" + str(datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"))
        file_name = name + ".xls"
        file_path = config.cache_dir("export_xls") / file_name
        print("export_csv",file_path)
        try:
            sheet = work.add_sheet("sheet1")
            data = []
            for obj in query:
                data.append(obj)
            if len(data) == 0:
                return ApiJsonResponse.error(ApiErrorCode.NOT_FOUND,"没有找到记录")
            fields = list(data[0].to_json().keys())
            
            sorted_fields = sorted(fields,key=lambda k:model.xls_sort_key(k) )
            
            for i,field in enumerate(sorted_fields):
                obj = data[0]
                remark = model.get_json_key_remark(obj,field)
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
            obj = self.model.objects.get(id=id)
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

    def delete(self, request: HttpRequest):
        id = request.GET.get("id")
        if request.method != "DELETE":
            return JsonResponse({"error": "only support DELETE"})
        print(self.model, "deleteApi")
        obj = self.model.objects.get(id=id)
        if obj is None:
            return JsonResponse({"error": "not found"})
        obj.delete()
        return JsonResponse(
            {
                "status": "success",
                "code": 200,
                "data": obj.to_json(),
            }
        )

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
    
