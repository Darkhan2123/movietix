from django.urls import path
from . import views

app_name = 'movies'

urlpatterns = [
    path('', views.movie_list_view, name='movie_list'),
    path('detail/<int:tmdb_id>/', views.movie_detail_view, name='movie_detail'),
    path('search/', views.search_results_view, name='search_results'),
]
