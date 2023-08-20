""" Adding cache, permissoin control, RESTful API to peewee

Peewee is a great ORM, and FastAPI is a great web framework. However, there
is a gap between them. Thousands of developers write their own caching, 
permission control, and biuld RESTful API for frontend. This library is
trying to fill the gap. Refer to example folder for usage.
"""
import ast
import base64
import hashlib
import logging
import operator
import pickle
import random
from functools import partialmethod, reduce
from itertools import combinations
from typing import List, Union, Dict

from peewee import OP, Expression, Field, Model, ModelSelect

__author__ = "Jianshuo Wang"
__copyright__ = "Copyright 2023, Baixing.com"
__credits__ = ["Jianshuo Wang", "Chato Development Team"]
__license__ = "MIT"
__version__ = "0.2"
__maintainer__ = "Jianshuo Wang"
__email__ = "jianshuo@hotmail.com"
__status__ = "Production"

logger = logging.getLogger(__name__)


def operator_name(op: ast.operator) -> str:
    """Get the operator name from the ast.operator

    Args:
        op (ast.operator): The operator from ast

    Returns:
        str: Upper case operator name like "AND" or "OR"

    >>> operator_name(ast.And())
    'AND'

    >>> operator_name(ast.Eq())
    '='

    """
    return OP.get(op.__class__.__name__.upper())


def expr(exp: Union[ast.AST, Expression, str], model: Model) -> Expression:
    """Convert an ast expression to a peewee expression

    I am surprised that no one actually created this function.

    >>> from peewee import CharField, IntegerField
    >>> class User(Model):
    ...     name = CharField()
    ...     age = IntegerField()
    >>> expr("name == 'John' and age > 18", User)  # doctest: +ELLIPSIS
    <peewee.Expression object at 0x...>

    Args:
        exp (Union[ast.AST, Expression, str]): _description_
        model (Model): _description_

    Raises:
        NotImplementedError: Not all ast expressions can map to
        peewee expressions. Raise this error if the ast expression
        is not supported yet.

    Returns:
        Expression: The peewee Expression
    """
    if isinstance(exp, str):
        return expr(ast.parse(exp, mode="eval").body, model)
    if isinstance(exp, ast.Constant):
        return exp.value
    if isinstance(exp, ast.Name):
        return getattr(model, exp.id)
    if isinstance(exp, (ast.Tuple, ast.List)):
        return [expr(e, model) for e in exp.elts]
    if isinstance(exp, ast.UnaryOp):
        return (
            expr(exp.operand, model).desc()
            if isinstance(exp.op, ast.USub)
            else expr(exp.operand, model).asc()
        )
    if isinstance(exp, ast.BoolOp):
        elements = [expr(e, model) for e in exp.values]
        return (
            reduce(operator.and_, elements)
            if isinstance(exp.op, ast.And)
            else reduce(operator.or_, elements)
        )
    if isinstance(exp, ast.Compare):
        return Expression(
            expr(exp.left, model),
            operator_name(exp.ops[0]),
            expr(exp.comparators[0], model),
        )
    raise NotImplementedError(f"Expression [{exp}] not supported yet")


def ensure_tuple(data) -> tuple:
    """Ensure the output is a tuple

    >>> ensure_tuple(1)
    (1,)

    >>> ensure_tuple([1, 2])
    (1, 2)

    >>> ensure_tuple((1, 2))
    (1, 2)

    Args:
        data (any): any data

    Returns:
        tuple: make sure the output is a tuple
    """
    if isinstance(data, (list, tuple)):
        return tuple(data)
    return (data,)


def field_eq(
    exp: Union[Expression, Field], field: Union[Field, str]
) -> Union[str, None]:
    """Get the value from the expression for the specified fields.
    For example, expression reprsentation of "a = 1 AND b = 2",
    and field = a will return "1".

    >>> from peewee import CharField, IntegerField
    >>> class User(Model):
    ...     name = CharField()
    ...     age = IntegerField()
    >>> field_eq(Expression(User.name, "=", "John"), "name")
    'John'

    >>> field_eq(Expression(Expression(User.name, "=", "John"),
    ...     'AND',
    ...     Expression(User.age, "=", 18)), "age")
    18

    Args:
        exp (Union[Expression, Field]): The expression to get the value from
        field (Union[Field, str]): The name or Field representing the field

    Returns:
        str | None: the value of the field, or None if not found
    """
    if isinstance(exp, Expression):
        if exp.op == "AND":
            return field_eq(exp.lhs, field) or field_eq(exp.rhs, field)
        if exp.op == "=":
            return exp.rhs if exp.lhs.name in field_names([field])[0] else None
    return None


def field_names(fields: List[Union[Field, str]]) -> List[str]:
    """Get the string names of the fields

    >>> field_names(["a", "b"])
    ['a', 'b']

    >>> from peewee import CharField, IntegerField
    >>> class User(Model):
    ...     name = CharField()
    ...     age = IntegerField()
    >>> field_names([User.name, User.age])
    ['name', 'age']

    Args:
        fields (List[Union[Field, str]]): The fields to get the names from

    Returns:
        List[str]: A list of string names of the fields
    """
    return [f.name if isinstance(f, Field) else f.strip() for f in fields]


def all_combinations(names: List[str]) -> List[tuple]:
    """Generate all combinations of the names, from empty set, to two,
    three or more elements of combinations, until the result is the same
    length as the list.

    >>> list(all_combinations(["a", "b"]))
    [(), ('a',), ('b',), ('a', 'b')]

    >>> list(all_combinations([]))
    [()]

    Args:
        names (List[str]): The elements to generate combinations from

    Yields:
        List[tuple[str]]: The combinations of the names
    """
    for i in range(len(names) + 1):
        yield from combinations(names, i)


def md5(data: str) -> str:
    """Generate the md5 hash of the data

    Args:
        data (str): The data

    Returns:
        str: The md5 hash
    """
    return hashlib.md5(data.encode("UTF-8")).hexdigest()


def flat(items: dict, sep: str = "=", join: str = ":") -> str:
    """Flatten a dictionary to a string. Key and value are separated by `sep`,
    and each key-value pair is separated by `join`.

    >>> flat({"a": 1, "b": 2})
    'a=1:b=2'

    >>> flat({"a": 1, "b": 2}, sep=":", join="=")
    'a:1=b:2'

    Args:
        items (dict): the dictionary to flatten
        sep (str, optional): the seperator. Defaults to "=".
        join (_type_, optional): the joiner. Defaults to ":".

    Returns:
        str: the flattened string
    """
    items = items or {}
    return join.join([f"{key}{sep}{value}" for key, value in items.items()])


def getattrs(obj: Union[dict, object, Expression], names: List[str]) -> dict:
    """A helper to get the attributes from an object, a dict or
    an peewee expression.

    >>> getattrs({"a": 1, "b": 2, "c": 3}, ["a", "b"])
    {'a': 1, 'b': 2}

    >>> class User:
    ...     def __init__(self, name, age):
    ...         self.name = name
    ...         self.age = age
    >>> getattrs(User("John", 20), ["name", "age"])
    {'name': 'John', 'age': 20}


    Args:
        obj (Union[dict, object, Expression]): the object to
            get the attributes from
        names (List[str]): the names to get attrabutes for

    Returns:
        dict: a dict with names as keys, and values as values
    """
    if isinstance(obj, dict):
        return {name: obj.get(name) for name in names if name in obj}
    if isinstance(obj, Expression):
        return {name: field_eq(obj, name) for name in names if field_eq(obj, name)}
    if isinstance(obj, object):
        return {name: getattr(obj, name) for name in names if hasattr(obj, name)}
    return {}


class MemoryStore(dict):
    """A memory version of Redis store."""

    def hget(self, key: str, tag: str):
        """Get the value of the key and tag from memory store.

        >>> m = MemoryStore()
        >>> m.hset("key", "tag", "This is the data")
        >>> m.hget("key", "tag")
        'This is the data'

        Args:
            key (str): the key
            tag (str): a sub key

        Returns:
            str: the stored data
        """
        return self.get(key, {}).get(tag)

    def hset(self, key: str, tag: str, value: str):
        """Set the value of the key and tag in memory store.

        Args:
            key (str): key
            tag (str): sub key
            value (str): The value to be set into the memory store
        """
        self.setdefault(key, {})[tag] = value

    def delete(self, *keys) -> None:
        """Delete the specified keys from the memory store.
        Clear the whole store once for every 1000 calls,
        to avoid memory leak.

        Args:
            *keys: the keys to be cleared
        """
        for key in keys:
            self.pop(key, None)

        if random.randint(1, 1000) == 1:
            self.clear()


class Cache:
    _store = MemoryStore()

    @classmethod
    def set_store(cls, store: object):
        """Set the store for the cache. It should be an instance of Redis
        or MemoryStore that implement hget, hset, and delete functions.
        Redis is preferred sicne MemoryStore can only work on a single
        server. If you are using multiple servers, you should use Redis.

        Args:
            store (object): MemoryStore or Redis
        """
        cls._store = store

    @classmethod
    def get_key(cls, key: str, sub_keys: dict = None):
        """Get the key for the cache. It is the class name, the key,
        and the sub keys.

        >>> Cache.get_key("key", {"a": 1, "b": 2})
        'Cache:key:a=1:b=2'

        >>> Cache.get_key("key")
        'Cache:key:'

        >>> Cache.get_key("key", {})
        'Cache:key:'

        >>> Cache.get_key("key", None)
        'Cache:key:'

        Args:
            key (str): the key
            sub_keys (dict, optional): the sub keys. Defaults to None.

        Returns:
            str: the key
        """
        return f"{cls.__name__}:{key}:{flat(sub_keys)}"

    @classmethod
    def dumps(cls, data: any) -> str:
        """Dumps the data to a string so that it can be stored in
        cache system like Redis.

        Args:
            data (any): the data to be dumped

        Returns:
            str: the dumped data
        """
        return base64.encodebytes(pickle.dumps(data))

    @classmethod
    def loads(cls, value: str) -> any:
        """Loads the data from a string.

        Args:
            value (str): the string to be loaded

        Returns:
            any: the loaded data
        """
        return pickle.loads(base64.decodebytes(value))

    @classmethod
    def get_cache(
        cls,
        key: str,
        func: callable,
        *args,
        tag: str = "-",
        sub_keys: dict = None,
        **kwargs,
    ) -> any:
        """Get the data from cache. If the data is not in cache,
        call the function to get the data, and store it in cache.
        The *args, and **kwargs will be passed to func().

        >>> Cache.get_cache("key", lambda: "This is the data")
        'This is the data'
        >>> Cache.get_cache("key", operator.add, 1, 3)
        'This is the data'
        >>> Cache.clear_cache("key")
        >>> Cache.get_cache("key", operator.add, 1, 3)
        4
        >>> Cache.clear_cache(Cache.get_key("key"), raw_key=True)
        >>> Cache.get_cache("key", operator.add, 1, 4)
        5

        Args:
            key (str): the key
            func (callable): the function to get the data
            tag (str, optional): the tag to use as hash key. Defaults to "-".
            sub_keys (dict, optional): the sub keys. Defaults to None.

        Returns:
            any: the data
        """
        key = cls.get_key(key, sub_keys)
        if value := cls._store.hget(key, tag):
            logger.debug(f"Cache HIT {key} {tag} {value[:20]}...")
            return cls.loads(value)

        data = func(*args, **kwargs)
        cls._store.hset(key, tag, cls.dumps(data))
        logger.debug(f"Cache MISS {key} {tag}")
        return data

    @classmethod
    def clear_cache(cls, *keys, raw_key=False):
        """Clear the cache for the specified keys.

        Args:
            *keys: the keys to be cleared
            raw_key (bool, optional): whether the key is raw key
            or needs to be prefixed by get_key() . Defaults to False.
        """
        cls._store.delete(*[key if raw_key else cls.get_key(key) for key in keys])


class CachedModelSelect(ModelSelect, Cache):
    def __iter__(self):
        """Iterate through the results with cache enabled.

        The cache key is the model name, suffixed by the indexed fields
        and values in the where clause. The cache tag is the md5 of the
        whole SQL text.

        For example, if the model name is "User", and the where clause
        is "User.id == 1", the cache key is "Cache:User:id=1", and the cache
        tag is the md5 of the whole SQL text.

        Please is a sample Cache Key, and Tag:

        Key: CachedModelSelect:ChatoDomain:creator=3
        Tag: 65702969e839a655eeaea0e89243efe9

        Yields:
            list: the results of the SELECT query, served from cache
                if possible
        """
        assert len(self._from_list) == 1, "Only one table is allowed by cache"
        yield from self.get_cache(
            key=self._from_list[0].__name__,
            sub_keys=getattrs(self._where, field_names(self.model.index_fields())),
            tag=md5(self.sql_text()),
            func=lambda: list(super(ModelSelect, self).__iter__()),
        )

    def sql_text(self) -> str:
        """The SQL text of the SELECT query.

        Returns:
            str: the SQL text
        """
        t, d = self.sql()
        return t % tuple(d)

    def _call(self, func: str, *expressions):
        """Pass the arguments to the function, and return the result.
        Before doing that, make sure the expression is a tuple, and
        only call the function if the first expression is not None."""

        if expressions and expressions[0] is not None:
            if isinstance(expressions[0], str):
                expressions = ensure_tuple(expr(expressions[0], self.model))
            return getattr(super(), func)(*expressions)
        return self

    where = partialmethod(_call, "where")
    select = partialmethod(_call, "select")
    order_by = partialmethod(_call, "order_by")


class CachedModel(Model, Cache):
    @classmethod
    def get_by_id(cls, id: int):
        """Get the model by id with cache enabled."""
        return cls.get_cache(id, super().get_by_id, id)

    def save(self, *args, **kwargs):
        """Save the model with cache enabled.

        Returns:
            int: the number of row saved
        """
        self.clear_cache(*self.cache_keys(), raw_key=True)
        return super().save(*args, **kwargs)

    @classmethod
    def index_fields(cls) -> List[Field]:
        """Returns a list of fields that are marked as index in the model.

        Returns:
            List[Field]: the list of fields that are marked as index
        """
        return [f for f in cls._meta.sorted_fields if f.index]

    def cache_keys(self) -> List[str]:
        """Returns a list of cache keys for the model.
        It caculate which content of the cache keys MAY be changed because
        of the save. For example, if the model is "User", and the index
        fields are "id" and "name", the following cache keys may contains
        invalid data:
            Cache:User: (The whole User table)
            CachedModelSelect:User:id=1:name=John
            CachedModelSelect:User:id=1
            CachedModelSelect:User:name=John

        Depending on whether id, or name, or both id and name appeared in
        the SELECT query, the data may be stored in either of the keys. We
        just cleared all the possible combination to be safe - the clear
        operation is cheap in Redis anyway.
        """
        yield self.get_key(self.id),
        for keys in all_combinations(field_names(self.index_fields())):
            yield CachedModelSelect.get_key(
                self.__class__.__name__, getattrs(self, keys)
            )

    @classmethod
    def select(cls, *fields) -> CachedModelSelect:
        """A small operation to create a CachedModelSelect (our Cached Version)
        instead of the default ModelSelect.

        I just copied the code from Model.select() and replaced the ModelSelect

        Returns:
            CachedModelSelect: the CachedModelSelect
        """
        if not fields:
            fields = cls._meta.sorted_fields
        return CachedModelSelect(cls, fields)


class PermissionedModel(Model):
    """A Model with permission control. It is used to control the
    permission of the model, and the fields of the model.

    The permission is defined following the Unix UGO permission model.
    The permission is defined as a 3-digit octal number, where the
    first digit is the permission for the owner, the second digit is
    the permission for the group, and the third digit is the permission
    for the other users. For each digit, the value is the sum of the
    following values:
        4: READ
        2: WRITE
        1: NOT DEFINED (Please keep it 0 all the time, and may be used
            for future extension)

    The model permission is defined as "permission" in Meta class.

    class User(Model):
        class Meta:
            permission = 0o606

    The field permission is defined as "_hidden" in Field class:

    class User(Model):
        name = CharField(max_length=100, _hidden=0o604)
        mobile = CharField(max_length=100, _hidden=0o600)
        role = CharField(max_length=100, _hidden=0o404)

    The permission above spefieid everyone can read the name, role,
    but only the owner (the user him/herself) can read the mobile.
    The owner can also write the name, mobile, but not role.

    The permission is defined in the following order:
        1. The default permission for the model
        2. The permission for the field
        3. The permission for the role of the user
        4. The permission for the operation

    Raises:
        PermissionError: if the user does not has the permission
        for the model or the field, it will raise PermissionError.
    """

    default_model_permission = 0o606  # READ and WRITE
    default_field_permission = 0o604  # OWNER READ WRITE, OTHER READ
    default_role = 0o007  # OTHER

    def get_role(self, user_id: int) -> int:
        """The role of the user. It is used to determine the permission
        of the user. Override this function to implement your own role
        management in subclasses.

        Args:
            user_id (int): the user id

        Returns:
            int: the role of the user
        """
        return self.default_role

    @classmethod
    def fields(cls, op_perm: int = 0, role: int = 0) -> List[Field]:
        """Returns a list of fields that the user has the permission
        to read/write.

        Args:
            op_perm (int, optional): the required permission. Defaults to 0.
            role (int, optional): the required role. Defaults to 0.

        Returns:
            List[Field]: the list of fields that the user has the permission
                to read/write.

        >>> from peewee import CharField
        >>> class User(Model):
        ...     name = CharField(max_length=100, _hidden=0o604)
        ...     mobile = CharField(max_length=100, _hidden=0o600)
        ...     role = CharField(max_length=100, _hidden=0o404)
        ...     class Meta:
        ...         permission = 0o600

        Check what fields the user can write (0o200):
        >>> User.fields(op_perm=0o200, role=0o700)
        [<AutoField: User.id>, <CharField: User.name>, <CharField: User.mobile>]
        """

        return [
            field
            for field, permission in cls.field_perms().items()
            if permission & op_perm & role
        ]

    @classmethod
    def field_perms(cls) -> Dict[Field, int]:
        """Returns a dict of fields and their permission.

        Returns:
            Dict[Field, int]: a dict of fields and their permission

        >>> from peewee import CharField
        >>> class User(Model):
        ...     name = CharField(max_length=100, _hidden=0o604)
        ...     mobile = CharField(max_length=100, _hidden=0o600)
        ...     role = CharField(max_length=100, _hidden=0o404)
        ...     class Meta:
        ...         permission = 0o600

        >>> User.field_perms()
        {<AutoField: User.id>: 384, <CharField: User.name>: 384, <CharField: User.mobile>: 384, <CharField: User.role>: 256}
        """
        return {f: cls.field_perm(f) for f in cls._meta.sorted_fields}

    @classmethod
    def field_perm(cls, field: Field) -> int:
        """Returns the permission of the field.

        Args:
            field (Field): the field

        Returns:
            _type_: the permission of the field

        >>> from peewee import CharField
        >>> class User(Model):
        ...     name = CharField(max_length=100, _hidden=0o604)
        ...     mobile = CharField(max_length=100, _hidden=0o600)
        ...     role = CharField(max_length=100, _hidden=0o404)
        ...     class Meta:
        ...         permission = 0o600

        >>> oct(User.field_perm(User.name))
        '0o600'

        """
        perm = cls.default_field_permission if field._hidden is False else field._hidden
        return perm & cls.model_perm()

    @classmethod
    def model_perm(cls) -> int:
        """Returns the permission of the model.

        >>> from peewee import CharField
        >>> class User(Model):
        ...     class Meta:
        ...         permission = 0o604
        >>> oct(User().model_perm())
        '0o604'
        """

        return getattr(cls._meta, "permission", cls.default_model_permission)

    def to_dict(
        self,
        user_id: int = 0,
        only: List[Union[Field, str]] = None,
        exclude: List[Field] = None,
    ) -> dict:
        """Returns a dict of the model. Only the fields that the user
        has the permission to read will be included.

        Args:
            user_id (int, optional): the user id. Defaults to 0.
            only (List[Union[Field, str]], optional): the list of fields
                to be included. Defaults to None. None or empty list means
                all fields.
            exclude (List[Field], optional): the list of fields to be
                excluded. Defaults to None.

        Returns:
            dict: a dict of the model


        >>> from peewee import CharField
        >>> class User(Model):
        ...     name = CharField(max_length=100, _hidden=0o604)
        ...     mobile = CharField(max_length=100, _hidden=0o600)
        ...     role = CharField(max_length=100, _hidden=0o404)
        ...     class Meta:
        ...         permission = 0o604
        >>> user = User()
        >>> user.name = "John"
        >>> user.mobile = "1234567890"
        >>> user.role = "user"

        OTHER user (default_role) can only read name and role:
        >>> user.to_dict(user_id=0)
        {'name': 'John', 'role': 'user'}

        >>> user.to_dict(user_id=0, only=["name"])
        {'name': 'John'}

        The mobile is not available for OTHER user, and name is excluded:
        >>> user.to_dict(user_id=0, exclude=["name"])
        {'role': 'user'}
        """
        readable_fields = field_names(self.fields(0o444, self.get_role(user_id)))
        readable_fields = [
            field
            for field in readable_fields
            if (only is None or not any(only) or field in field_names(only))
            and (exclude is None or field not in field_names(exclude))
        ]

        return getattrs(self.__data__, readable_fields)

    def from_dict(self, items: dict, user_id: int = 0) -> "PermissionedModel":
        """Update the model from a dict. Only the fields that the user
        has the permission to write will be updated. If the user does
        not have the permission to write the field, it will raise
        PermissionError.

        Args:
            items (dict): the dict to update the model
            user_id (int, optional): the user id. Defaults to 0.

        Raises:
            PermissionError: if the user does not have the permission
                to write the field, it will raise PermissionError.

        Returns:
            PermissionedModel: the updated model

        >>> from peewee import CharField
        >>> class User(Model):
        ...     name = CharField(max_length=100, _hidden=0o604)
        ...     mobile = CharField(max_length=100, _hidden=0o600)
        ...     role = CharField(max_length=100, _hidden=0o404)
        ...     class Meta:
        ...         permission = 0o604
        >>> user = User()
        >>> props = {"name": "John", "mobile": "1234567890", "role": "admin"}
        >>> user.from_dict(props, user_id=0)
        Traceback (most recent call last):
        ...
        PermissionError: Field name is not writable for user 0
        >>> user.from_dict(props, user_id=1)
        Traceback (most recent call last):
        ...
        PermissionError: Field name is not writable for user 1


        """
        writable_fields = self.fields(0o222, self.get_role(user_id))
        for key, value in items.items():
            if key in field_names(writable_fields):
                setattr(self, key, value)
            else:
                raise PermissionError(f"Field {key} is not writable for user {user_id}")
        return self


class BaseModel(PermissionedModel, CachedModel, Model):
    """The final model that is used in the application. It is a
    combination of PermissionedModel and CachedModel.

    Any sub class Model will have the following features out of box.
        1. Permission control
        2. Cache control
    """

    pass
