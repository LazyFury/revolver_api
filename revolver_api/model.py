import datetime
from django.db import models
from logging import warn


class SerializerModel(models.Model):
    class Meta:
        abstract = True
        
    def fillable(self):
        """ 可填充字段

        Returns:
            _type_: 返回可填充字段列表
        """
        return [f.name for f in self.get_fields() if f.name not in self.exclude_fillable()]
    
    def exclude_fillable(self):
        """ 不可填充字段

        Returns:
            _type_: 返回不可填充字段列表
        """
        return ["id", "created_at", "updated_at", "is_deleted"]

    def convert(self,obj):
        """ 转换为json时处理特殊类型

        Args:
            obj (_type_): _description_

        Returns:
            _type_: _description_
        """
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
        """ 转换为json

        Returns:
            _type_: _description_
        """
        return self.sample_to_json(*args, **kwargs)
    
    def xls_key_mapping(self):
        """ xls key 映射

        Returns:
            _type_: _description_
        """
        return {
            "id": "ID",
            "created_at": "创建时间",
            "updated_at": "更新时间",
            "is_deleted": "是否删除",
        }
    
    @staticmethod
    def to_xls_format(obj,key):
        """ 转换为xls格式

        Args:
            obj (_type_): _description_
            key (_type_): _description_

        Returns:
            _type_: _description_
        """
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
        # num 
        if isinstance(val,int):
            return val
        if isinstance(val,float):
            return val
        if isinstance(val,str):
            return val if val != "" else "/"
        return val.__str__() if val is not None else "/"
    
    def get_xls_key_remark(self, key):
        """ 获取xls key 备注

        Args:
            key (_type_): _description_

        Returns:
            _type_: _description_
        """
        return self.xls_key_mapping().get(key, key)

    
    
    @staticmethod
    def xls_sort_key(key):
        """ xls 排序key

        Args:
            key (_type_): _description_

        Returns:
            _type_: _description_
        """
        return {
            "id": 0,
            "created_at": 1,
            "updated_at": 2,
            "is_deleted": 3,
        }.get(key, 999)

    def serialize(
        self, with_foreign=True, with_related=False, related_serializer=False
    ):
        """遍历所有属性

        Returns:
            _type_: _description_
        """
        for field in self.get_fields():
            key = field.name
            if hasattr(self, key) and key not in self.exclude_json_keys():
                res = getattr(self, key)
                yield key, self.convert(res) if res is not None else None
                
        # foreign_ids 
        for field in self.foreign_fields():
            key = f"{field.name}_id"
            if hasattr(self, key):
                res = getattr(self, key)
                yield key, self.convert(res) if res is not None else None
                
                
        # print(self.foreignKeys())
        for field in self.foreign_fields():
            if hasattr(self, field.name) and with_foreign is True:
                foreign:SerializerModel = getattr(self, field.name)
                # print("foreign", fKey.name, foreign)
                # one to one
                if hasattr(foreign, "sample_to_json"):
                    yield (
                        field.name,
                        foreign.sample_to_json(
                            with_foreign=True,
                            related_serializer=False,
                            with_related=True,
                        ),
                    )
                else:
                    # 可能是被别的对象引用或者 None ，被别的对象引用的话，这里是一个 RelatedManager 对象,不适合自动处理
                    yield (field.name, None)
            # related one to many
            if field.related_model is not None and with_related is True:
                related:SerializerModel = field.related_model
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
                yield field.name, arr
                yield field.name + "_count", len(arr)

    def extra_json(self):
        return {}

    def get_fields(self):
        return [f for f in self._meta.get_fields() if f.is_relation is False]

    def foreign_fields(self):
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
            for key, value in self.serialize(
                with_foreign=with_foreign,
                with_related=with_related,
                related_serializer=related_serializer,
            )
        }

        # merge extra key 
        for key, value in self.extra_json().items():
            if merge_force is True:
                result[key] = value
            else:
                if result.get(key) is None:
                    result[key] = value
                else:
                    warn("key %s is exists" % key)
                
        return result

