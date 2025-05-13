from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import Permission, Group

from django_resized import ResizedImageField
from phonenumber_field.modelfields import PhoneNumberField

from .managers import UserManager


class User(AbstractUser):
    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'
        ordering = ('-date_joined',)

    username = None
    email = models.EmailField(verbose_name='электронная почта', unique=True, blank=False, null=False)
    avatar = ResizedImageField(size=[500, 500], crop=['middle', 'center'], upload_to='avatars/',
                               force_format='WEBP', quality=90, verbose_name='аватарка',
                               null=True, blank=True)
    phone = PhoneNumberField(max_length=100, unique=True, verbose_name='номер телефона', blank=True, null=True)

    groups = models.ManyToManyField(Group, related_name='account_users', blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name='account_users_permissions', blank=True)
    dashboard = models.ForeignKey('chatbot.Dashboard', on_delete=models.SET_NULL, related_name='members', null=True, blank=True)

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f'{str(self.email) or self.first_name}'