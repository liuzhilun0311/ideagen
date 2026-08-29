from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '确保 admin 账号存在（用 ADMIN_PASSWORD 环境变量或 settings.ADMIN_PASSWORD）'

    def handle(self, *args, **options):
        from accounts.auth import ensure_admin
        admin_user = ensure_admin()
        if admin_user:
            self.stdout.write(self.style.SUCCESS(f"已创建 admin 账号: {admin_user['username']}"))
        else:
            self.stdout.write("admin 账号已存在，跳过")
