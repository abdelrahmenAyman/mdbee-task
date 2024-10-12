from django.shortcuts import render


def index(request):
    return render(request, "file_listener/index.html")
