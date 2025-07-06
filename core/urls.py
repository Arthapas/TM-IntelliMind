from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('create-insight/', views.create_insight, name='create_insight'),
    path('meeting/<uuid:meeting_id>/', views.meeting_detail, name='meeting_detail'),
    path('meeting/<uuid:meeting_id>/delete/', views.delete_meeting, name='delete_meeting'),
    path('upload-audio/', views.upload_audio, name='upload_audio'),
    path('start-transcription/', views.start_transcription, name='start_transcription'),
    path('transcription-progress/', views.transcription_progress, name='transcription_progress'),
    path('generate-insights/', views.generate_insights, name='generate_insights'),
    path('insights-progress/', views.insights_progress, name='insights_progress'),
    path('save-analysis/', views.save_analysis, name='save_analysis'),
]