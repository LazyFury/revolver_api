import datetime
import time
from django.db import models
from logging import warn

from django.http import HttpRequest, HttpResponse

from core import config
from revolver_api.revolver_api.response import ApiErrorCode, ApiJsonResponse



class SerializerModel(models.Model):
    class Meta:
        abstract = True

    def convert(self,obj):
        # warn("【You should override this method】 convert %s" % obj,)
        # bool 
        if isinstance(obj,bool):
            return obj
        # int
        if isinstance(obj,int):
            return obj
        # none 
        if obj is None:
            return obj
        return obj if isinstance(obj,str) else obj.__str__()
    
    def to_json(self, *args, **kwargs):
        return self.sample_to_json(*args, **kwargs)
    
    def json_key_remark(self):
        return {
            "id": "ID",
            "created_at": "创建时间",
            "updated_at": "更新时间",
            "is_deleted": "是否删除",
        }
    
    @staticmethod
    def to_xls_format(obj,key):
        if key not in obj:
            return "-"
        val = obj.get(key,"/")
        if isinstance(val,datetime.datetime):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(val,datetime.date):
            return val.strftime("%Y-%m-%d")
        # bool 
        if isinstance(val,bool):
            return "是" if val else "否"
        return val.__str__() if val is not None and val != "" else "/"
    
    def get_json_key_remark(self, key):
        return self.json_key_remark().get(key, key)
    
    @staticmethod
    def xls_sort_key(key):
        return {
            "id": 0,
            "created_at": 1,
            "updated_at": 2,
            "is_deleted": 3,
        }.get(key, 999)

    def loop_all_self_attr(
        self, with_foreign=True, with_related=False, related_serializer=False
    ):
        """遍历所有属性

        Returns:
            _type_: _description_
        """
        for key in self.__dict__:
            if hasattr(self, key):
                if key == "_state":
                    continue
                res = getattr(self, key)
                # test type res
                
                yield key, self.convert(res) if res is not None else None
        # print(self.foreignKeys())
        for fKey in self.foreignKeys():
            if hasattr(self, fKey.name) and with_foreign is True:
                foreign = getattr(self, fKey.name)
                # print("foreign", fKey.name, foreign)
                # one to one
                if hasattr(foreign, "sample_to_json"):
                    yield (
                        fKey.name,
                        getattr(self, fKey.name).sample_to_json(
                            with_foreign=True,
                            related_serializer=False,
                            with_related=True,
                        ),
                    )
                else:
                    # res = getattr(self, fKey.name)
                    # yield (
                    #     fKey.name,
                    #     res.__str__() if res is not None else None,
                    # )
                    # 可能是被别的对象引用或者 None ，被别的对象引用的话，这里是一个 RelatedManager 对象,不适合自动处理
                    yield (fKey.name, None)
            # related one to many
            if fKey.related_model is not None and with_related is True:
                related = fKey.related_model
                # print(self.__class__.__name__, fKey.name, related.__class__.__name__)
                arr = []
                if hasattr(related, self.__class__.__name__.lower()) is False:
                    continue

                for item in related.objects.filter(
                    **{self.__class__.__name__.lower(): self}
                ).all():
                    if item is not None and hasattr(item, "sample_to_json"):
                        if related_serializer is True:
                            arr.append(
                                item.sample_to_json(  # type: ignore
                                    with_foreign=False,
                                    related_serializer=False,
                                    with_related=False,
                                )  # type: ignore
                            )
                            continue
                        arr.append(item.__str__())
                yield fKey.name, arr
                yield fKey.name + "_count", len(arr)

    def extra_json(self):
        return {}

    def foreignKeys(self):
        return [f for f in self._meta.get_fields() if f.is_relation]

    def exclude_json_keys(self):
        return ["is_deleted", "password"]

    def sample_to_json(
        self,
        with_foreign=True,
        with_related=True,
        related_serializer=False,
        merge_force=False,
    ):
        """转换为json

        Returns:
            _type_: _description_
        """
        result = {
            key: value
            for key, value in self.loop_all_self_attr(
                with_foreign=with_foreign,
                with_related=with_related,
                related_serializer=related_serializer,
            )
        }

        for key, value in self.extra_json().items():
            if merge_force is True:
                result[key] = value
            else:
                if result.get(key) is None:
                    result[key] = value
                else:
                    warn("key %s is exists" % key)
        for key in self.exclude_json_keys():
            if result.keys().__contains__(key):
                del result[key]
        return result

