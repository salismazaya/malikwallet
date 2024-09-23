import traceback
from main.models import ErrorLog

class ErrorLogger:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        ErrorLog.objects.create(
            error = traceback.format_exc()
        )
