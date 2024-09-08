from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import os
from os import getenv
from pytube import YouTube
from pytubefix import YouTube
from pytubefix.cli import on_progress
from django.conf import settings
import assemblyai as aai
from dotenv import load_dotenv
from openai import OpenAI
from .models import BlogPost

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            yt_link = data["link"]
            
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({"error" : "Invalid request method"}, status=400)
        
        # get yt title
        title = yt_title(yt_link)

        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({"error" : "Failed to get transscript"}, status=500)

        # use OpenAI to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({"error" : "Failed to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content
        )
        new_blog_article.save()

        # return blog article as response
        return JsonResponse({"content" : str(blog_content)})
    else:
        return JsonResponse({"error" : "Invalid request method"}, status=405)
    
def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title

def download_audio(link):
    yt = YouTube(link, on_progress_callback = on_progress)
    print(yt.title)
    
    ys = yt.streams.get_audio_only()
    out_file = ys.download(mp3=True, output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + '.mp3'
    os.rename(out_file, new_file)
    return new_file

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

    print("Transcribing...")
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    with open("transcript.txt", "w") as file:
        file.write(transcript.text)
    return transcript.text

def generate_blog_from_transcription(transcription):
    openai_api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(
        api_key=openai_api_key
    )

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000
        )
    except Exception as e:
        print("An error appeared: ", e)

    generated_content = completion.choices[0].message.content

    return generated_content


def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {"blog_articles" : blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect("/")

def user_login(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("/")
        else:
            error_msg = "Invalid username or password"
            return render(request, "login.html", {"error_message" : error_msg})
    return render(request, "login.html")

def user_signup(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]
        repeatPassword = request.POST["repeatPassword"]

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect("/")
            except:
                error_msg = "Error creating account"
                return render(request, "signup.html", {"error_message" : error_msg})
        else:
            error_msg = "Passwords do not match"
            return render(request, "signup.html", {"error_message" : error_msg})
    return render(request, "signup.html")

def user_logout(request):
    logout(request)
    return redirect("/")