"""用户与 Token 数据模型（与 Flask 版 users.json 结构一致）。"""
from django.db import models


class User(models.Model):
    """用户账号。"""
    id = models.CharField(max_length=64, primary_key=True)          # u_<hex>
    username = models.CharField(max_length=64, unique=True)
    password_hash = models.CharField(max_length=256)                # pbkdf2:sha256:200000$<salt>$<hash>
    created_at = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    use_shared_config = models.BooleanField(default=True)           # 是否使用共享服务商配置

    class Meta:
        db_table = 'account_user'

    def __str__(self):
        return self.username


class Token(models.Model):
    """登录令牌（Bearer token，7 天有效期）。"""
    key = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tokens')
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'account_token'

    def __str__(self):
        return f"{self.user.username}:{self.key[:8]}..."
