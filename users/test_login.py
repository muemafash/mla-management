# users/test_login.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def test_login(request):
    if request.method == 'POST':
        return JsonResponse({'message': 'POST request received'})
    return JsonResponse({'message': 'GET request received'})