import json
import pickle
import re
import threading
import time
from collections import namedtuple
from contextlib import suppress

import redis
import redis.exceptions
from redis.commands.search import Search
from redis.exceptions import ResponseError

# import frappe
from .utils import cstr

# 5 is faster than default which is 4.
# Python uses old protocol for backward compatibility, we don't support anything <3.10.
DEFAULT_PICKLE_PROTOCOL = 5


class RedisearchWrapper(Search):
    def sugadd(self, key, *suggestions, **kwargs):
        return super().sugadd(self.client.make_key(key), *suggestions, **kwargs)

    def suglen(self, key):
        return super().suglen(self.client.make_key(key))

    def sugdel(self, key, string):
        return super().sugdel(self.client.make_key(key), string)

    def sugget(self, key, *args, **kwargs):
        return super().sugget(self.client.make_key(key), *args, **kwargs)


class RedisWrapper(redis.Redis):
    """Redis client that will automatically prefix conf.db_name"""

    def connected(self):
        try:
            self.ping()
            return True
        except redis.exceptions.ConnectionError:
            return False

    def __call__(self):
        """WARNING: Added for backward compatibility to support cache().method(...)"""
        return self

    def make_key(self, key, user=None, shared=False):
        if shared:
            return key

        if user:
            # if user is True:
            # 	user = frappe.local.session.get("user")

            key = f"user:{user}:{key}"

        return f"trakla|{key}".encode()

    def set_value(self, key, val, user=None, expires_in_sec=None, shared=False):
        """Sets cache value.

        :param key: Cache key
        :param val: Value to be cached
        :param user: Prepends key with User
        :param expires_in_sec: Expire value of this key in X seconds
        """
        key = self.make_key(key, user, shared)

        # frappe.local.cache[key] = val
        with suppress(redis.exceptions.ConnectionError):
            self.set(name=key, value=pickle.dumps(val, protocol=DEFAULT_PICKLE_PROTOCOL), ex=expires_in_sec)

    def get_value(self, key, generator=None, user=None, expires=False, shared=False, *, use_local_cache=True):
        """Return cache value. If not found and generator function is
                given, call the generator.

        :param key: Cache key.
        :param generator: Function to be called to generate a value if `None` is returned.
        :param expires: If the key is supposed to be with an expiry, don't store it in frappe.local
        """
        original_key = key
        key = self.make_key(key, user, shared)

        # local_cache = frappe.local.cache
        # if key in local_cache and use_local_cache:
        # 	val = local_cache[key]

        # else:
        val = None
        try:
            val = self.get(key)
        except redis.exceptions.ConnectionError:
            pass

        if val is not None:
            val = pickle.loads(val)

        if not expires:
            if val is None and generator:
                val = generator()
                self.set_value(original_key, val, user=user, shared=shared)

            # else:
            #     local_cache[key] = val

        return val

    def expire_key(self, key, time, *, user=None, shared=False):
        key = self.make_key(key, user, shared)
        try:
            return self.expire(key, time)
        except redis.exceptions.ConnectionError:
            pass

    def get_all(self, key):
        ret = {}
        for k in self.get_keys(key):
            ret[key] = self.get_value(k)

        return ret

    def get_keys(self, key, user=None, shared=False):
        """Return keys starting with `key`."""
        try:
            key = self.make_key(key + "*", user=user, shared=shared)
            return self.keys(key)

        except redis.exceptions.ConnectionError:
            # regex = re.compile(cstr(key).replace("|", r"\|").replace("*", r"[\w]*"))
            # return [k for k in list(frappe.local.cache) if regex.match(cstr(k))]
            return []

    def delete_keys(self, key, user=None, shared=False):
        """Delete keys with wildcard `*`."""
        self.delete_value(self.get_keys(key, user=user, shared=shared), make_keys=False)

    def delete_key(self, *args, **kwargs):
        self.delete_value(*args, **kwargs)

    def delete_value(self, keys, user=None, make_keys=True, shared=False):
        """Delete value, list of values."""
        if not keys:
            return

        if not isinstance(keys, list | tuple):
            keys = (keys,)

        if make_keys:
            keys = [self.make_key(k, shared=shared, user=user) for k in keys]

        # local_cache = frappe.local.cache
        # for key in keys:
        #     local_cache.pop(key, None)

        try:
            self.unlink(*keys)
        except redis.exceptions.ConnectionError:
            pass

    def lpush(self, key, value, user=None, shared=False):
        return super().lpush(self.make_key(key, user=user, shared=shared), value)

    def rpush(self, key, value):
        return super().rpush(self.make_key(key), value)

    def lpop(self, key, user=None, shared=False):
        return super().lpop(self.make_key(key, user=user, shared=shared))

    def rpop(self, key):
        return super().rpop(self.make_key(key))

    def blpop(self, key, timeout=0, user=None, shared=False):
        return super().blpop(self.make_key(key, user=user, shared=shared), timeout=timeout)

    def llen(self, key):
        return super().llen(self.make_key(key))

    def lrange(self, key, start, stop):
        return super().lrange(self.make_key(key), start, stop)

    def ltrim(self, key, start, stop):
        return super().ltrim(self.make_key(key), start, stop)

    def hset(
        self,
        name: str,
        key: str,
        value,
        shared: bool = False,
        *args,
        **kwargs,
    ):
        if key is None:
            return

        _name = self.make_key(name, shared=shared)

        # set in local
        # frappe.local.cache.setdefault(_name, {})[key] = value

        # set in redis
        try:
            super().hset(_name, key, pickle.dumps(value, protocol=DEFAULT_PICKLE_PROTOCOL), *args, **kwargs)
        except redis.exceptions.ConnectionError:
            pass

    def hexists(self, name: str, key: str, shared: bool = False) -> bool:
        if key is None:
            return False
        _name = self.make_key(name, shared=shared)
        try:
            return super().hexists(_name, key)
        except redis.exceptions.ConnectionError:
            return False

    def exists(self, *names: str, user=None, shared=None) -> int:
        names = [self.make_key(n, user=user, shared=shared) for n in names]

        try:
            return super().exists(*names)
        except redis.exceptions.ConnectionError:
            return False

    def hgetall(self, name):
        value = super().hgetall(self.make_key(name))
        return {key: pickle.loads(value) for key, value in value.items()}

    def hget(self, name, key, generator=None, shared=False):
        _name = self.make_key(name, shared=shared)

        # local_cache = frappe.local.cache
        # if _name not in local_cache:
        #     local_cache[_name] = {}

        if not key:
            return None

        # if key in local_cache[_name]:
        #     return local_cache[_name][key]

        value = None
        try:
            value = super().hget(_name, key)
        except redis.exceptions.ConnectionError:
            pass

        if value is not None:
            value = pickle.loads(value)
            # local_cache[_name][key] = value
        elif generator:
            value = generator()
            self.hset(name, key, value, shared=shared)
        return value

    def hdel(
        self,
        name: str,
        keys: str | list | tuple,
        shared=False,
        pipeline: redis.client.Pipeline | None = None,
    ):
        """
        A wrapper around redis' HDEL command

        :param name: The hash name
        :param keys: the keys to delete
        :param shared: shared frappe key or not
        :param pipeline: A redis.client.Pipeline object, if this transaction is to be run in a pipeline
        """
        _name = self.make_key(name, shared=shared)

        # name_in_local_cache = _name in frappe.local.cache

        if not isinstance(keys, list | tuple):
            # if name_in_local_cache and keys in frappe.local.cache[_name]:
            #     del frappe.local.cache[_name][keys]
            if pipeline:
                pipeline.hdel(_name, keys)
            else:
                try:
                    super().hdel(_name, keys)
                except redis.exceptions.ConnectionError:
                    pass
            return

        local_pipeline = False

        if pipeline is None:
            pipeline = self.pipeline()
            local_pipeline = True

        for key in keys:
            # if name_in_local_cache:
            #     if key in frappe.local.cache[_name]:
            #         del frappe.local.cache[_name][key]
            pipeline.hdel(_name, key)

        if local_pipeline:
            try:
                pipeline.execute()
            except redis.exceptions.ConnectionError:
                pass

    def hdel_names(self, names: list | tuple, key: str):
        """
        A function to call HDEL on multiple hash names with a common key, run in a single pipeline

        :param names: The hash names
        :param key: The common key
        """
        pipeline = self.pipeline()
        for name in names:
            self.hdel(name, key, pipeline=pipeline)
        try:
            pipeline.execute()
        except redis.exceptions.ConnectionError:
            pass

    def hdel_keys(self, name_starts_with, key):
        """Delete hash names with wildcard `*` and key"""
        pipeline = self.pipeline()
        for name in self.get_keys(name_starts_with):
            name = name.split("|", 1)[1]
            self.hdel(name, key, pipeline=pipeline)
        try:
            pipeline.execute()
        except redis.exceptions.ConnectionError:
            pass

    def hkeys(self, name):
        try:
            return super().hkeys(self.make_key(name))
        except redis.exceptions.ConnectionError:
            return []

    def sadd(self, name, *values):
        """Add a member/members to a given set"""
        super().sadd(self.make_key(name), *values)

    def srem(self, name, *values):
        """Remove a specific member/list of members from the set."""
        super().srem(self.make_key(name), *values)

    def sismember(self, name, value):
        """Return True or False based on if a given value is present in the set."""
        return super().sismember(self.make_key(name), value)

    def spop(self, name):
        """Remove and returns a random member from the set."""
        return super().spop(self.make_key(name))

    def srandmember(self, name, count=None):
        """Return a random member from the set."""
        return super().srandmember(self.make_key(name))

    def smembers(self, name):
        """Return all members of the set."""
        return super().smembers(self.make_key(name))

    def ft(self, index_name="idx"):
        return RedisearchWrapper(client=self, index_name=self.make_key(index_name))