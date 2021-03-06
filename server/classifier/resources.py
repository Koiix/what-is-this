import base64

from django.core import serializers
from django.core.files.base import ContentFile
from django.contrib.auth import authenticate, login, logout
from django.conf.urls import url
from django.http import HttpResponse

from tastypie import fields
from tastypie.authentication import ApiKeyAuthentication
from tastypie.http import HttpUnauthorized, HttpForbidden
from tastypie.resources import ModelResource
from tastypie.utils import trailing_slash
from tastypie.models import ApiKey

from classifier.authorization import UserOnlyAuthorization, ClassificationOnlyAuthorization
from classifier.models import Classification
from classifier.models import User

class UserResource(ModelResource):
    class Meta:
        queryset = User.objects.all()
        resource_name = 'user'
        excludes = ['email', 'first_name', 'last_name',  'is_staff',
        'groups', 'password', 'is_superuser', 'is_active', 'user_permission']
        allowed_methods = ['get']
        authentication = ApiKeyAuthentication()
        authorization = UserOnlyAuthorization()

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/login%s$" %
                (self._meta.resource_name, trailing_slash()), self.wrap_view('login'), name="user_login"),
            url(r"^(?P<resource_name>%s)/register%s$" % 
                (self._meta.resource_name, trailing_slash()), self.wrap_view('register'), name="user_register"),
            url(r"^(?P<resource_name>%s)/logout%s$" %
                (self._meta.resource_name, trailing_slash()), self.wrap_view('logout'), name="user_logout"),
            url(r"^(?P<resource_name>%s)/(?P<userid>\d+)/classifications%s$" %
                (self._meta.resource_name, trailing_slash()), self.wrap_view('list_classifications'), name="user_classifications")
        ]

    def login(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        data = self.deserialize(request, request.body, format = request.META.get('CONTENT_TYPE', 'application/json'))

        username = data.get('username', '')
        password = data.get('password', '')

        user = authenticate(username=username, password=password)

        if user:
            if user.is_active:
                login(request, user)
                api_key = ApiKey.objects.get_or_create(user=user)
                return self.create_response(request, {
                    'success': True,
                    'api_key': api_key[0].key,
                    'user': user.to_dict(),
                })
            else:
                return self.create_response(request, {
                    'success': False,
                    'reason': 'disabled',
                    }, HttpForbidden )
        else:
            return self.create_response(request, {
                'success': False,
                'reason': 'incorrect username/password',
                }, HttpUnauthorized )
    
    def register(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        data = self.deserialize(request, request.body, format = request.META.get('CONTENT_TYPE', 'application/json'))

        username = data.get('username', '')
        password = data.get('password', '')

        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            user = User.objects.create_user(username=username, password=password)
            if user:
                login(request, user)
                api_key = ApiKey.objects.get_or_create(user=user)
                return self.create_response(request, {
                    'success': True,
                    'api_key': api_key[0].key,
                    'user': user.to_dict()
                })
            else: 
                return self.create_response(request, {
                'success': False,
                'reason': 'failed',
                }, HttpForbidden )
        else:
            return self.create_response(request, {
                    'success': False,
                    'reason': 'User already exists!',
                    }, HttpForbidden )
    
    def logout(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        self.is_authenticated(request)

        if  request.user and request.user.is_authenticated:
            api_key = ApiKey.objects.get(user=request.user)
            api_key.key = None
            api_key.save()
            logout(request)
            return self.create_response(request, { 'success': True })
        else:
            return self.create_response(request, { 'success': False }, HttpUnauthorized)

    def list_classifications(self, request, **kwargs):
        self.method_check(request, allowed=['get'])

        self.is_authenticated(request)
        print(kwargs['userid'])
        if  request.user and request.user.is_authenticated:
            qs = Classification.objects.filter(user=User.objects.get(id=kwargs['userid']))
            return self.create_response(request, { 'success': True, 'objects': list(qs.values())})
        else:
            return self.create_response(request, { 'success': False }, HttpUnauthorized)  

class ClassificationResource(ModelResource):
    class Meta:
        queryset = Classification.objects.all()
        resource_name = 'classification'
        authentication = ApiKeyAuthentication()
        authorization = ClassificationOnlyAuthorization()

    def dehydrate(self, bundle):
        bundle.data['user_id'] = bundle.obj.user_id
        return bundle

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/create%s$" % (self._meta.resource_name, trailing_slash()), self.wrap_view('create'), name="classification_create")
        ]

    def create(self, request, **kwargs):
        self.method_check(request, allowed=['post'])

        data = self.deserialize(request, request.body, format = request.META.get('CONTENT_TYPE', 'application/json'))

        b64 = data.get('photo', '')

        self.is_authenticated(request)
        if  request.user and request.user.is_authenticated:
            
            format, imgstr = b64.split(';base64,') 
            ext = format.split('/')[-1] 
            c = Classification.objects.create(result="i have no clue", confidence="0% not at all", user=request.user)
            c.save()
            photo = ContentFile(base64.b64decode(imgstr), name= str(c.id) + '.' + ext)
            c.photo = photo
            c.save()
            return self.create_response(request, { 'success': True , 'classification': c.to_dict() })
        else:
            return self.create_response(request, { 'success': False }, HttpUnauthorized)
