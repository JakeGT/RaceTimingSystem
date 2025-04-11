#  running/app/urls.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import handler404, handler500, handler403
from django.urls import path, include
from .views import CustomPasswordResetView
from django.contrib.auth import views as auth_views


# -------------------------------------------------- Define URL Patterns -----------------------------------------------
urlpatterns = [

    # upload json of data
    path('race/<int:race_id>/upload', views.upload_json, name='upload_json'),

    #  landing page
    path('', views.landing_page, name='landing'),

    #  dashboard page
    path('dashboard/', views.dashboard, name='dashboard'),

    #  race configuration page
    path('race-config/', views.race_config, name='race_config'),

    #  participants upload page
    path('upload-participants/', views.upload_participants, name='upload_participants'),

    #  results upload page
    path('upload-results/', views.upload_results, name='upload_results'),

    #  user registration page
    path('register/', views.user_register, name='register'),

    #  user login page
    path('login/', views.user_login, name='login'),

    #  password reset custom view
    path("password_reset/", CustomPasswordResetView.as_view(), name="password_reset"),

    #  password reset-email sent page
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="app/password_reset_done.html"),
         name="password_reset_done"),

    #  confirming password reset request page
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(template_name="app/password_reset_confirm.html"),
         name="password_reset_confirm"),

    #  password reset complete page
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="app/password_reset_complete.html"),
         name="password_reset_complete"),

    #  user logout route
    path('logout/', views.user_logout, name='logout'),

    #  organiser management page
    path('manage_participants/<int:race_id>/', views.manage_participants, name='manage_participants'),

    #  race history page
    path('race-history/', views.race_history, name='race_history'),

    #  organiser dashboard page
    path('organiser-dashboard/', views.race_organiser_dashboard, name='race_organiser_dashboard'),

    #  race details page, including leaderboard
    path('race/<int:race_id>/', views.race_detail, name='race_detail'),

    #  upcoming races page
    path('upcoming-races', views.upcoming_races, name='upcoming_races'),

    #  user settings page
    path('settings', views.settings_view, name='settings'),

    #  user logged in password change pages
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),

    #  successful password reset page
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),

    #  user profile page
    path("profile/", views.profile_view, name="profile"),

    #  organiser race view page
    path('organiser/race/<int:race_id>/', views.organiser_race_detail, name='organiser_race_detail'),

    #  list of race categories page
    path('race-categories/', views.race_category_list, name='race_category_list'),

    #  creating new race category page
    path('race-categories/new/', views.race_category_create, name='race_category_create'),

    # participants categories page
    path('participants-categories/', views.participant_category_list, name='category_list'),

    #  creating new participants category page
    path('participants-categories/new/', views.participant_category_create, name='category_create'),

    #  page for adjusting the start time from which race times are calculated
    path('race/<int:race_id>/adjust_start_time/', views.adjust_start_time, name='adjust_start_time'),

    #  google sign in page
    path('google-login/callback/', views.google_callback, name='google_callback'),

    #  image upload endpoint
    path('upload-image/', views.upload_image, name='upload_image'),

    #  manual bib validation
    path('gallery/<int:race_id>/', views.gallery_view, name='gallery_view'),

    #  race deletion route
    path('race/<int:race_id>/delete/', views.organiser_delete_race, name='organiser_delete_race'),

    #  organiser application page
    path('organiser/apply/', views.apply_as_organiser, name='apply_as_organiser'),

    #  organiser application viewing page
    path('organiser/applications/', views.view_applications, name='view_applications'),

    #  individual organiser application page
    path('organiser/applications/<int:app_id>/<str:action>/', views.handle_application, name='handle_application'),

    #  log in with facebook account route
    path('facebook-login/', lambda request: redirect('/accounts/facebook/login/'), name='facebook_login'),

    #  social-auth route for third party sign in
    path('social-auth/', include('social_django.urls', namespace='social')),

    #  2fa route
    path('verify-2fa/', views.verify_2fa_view, name='verify_2fa'),

    #  participant deletion confirmation page
    path('race/<int:race_id>/delete_participant/<int:participant_id>/', views.confirm_delete_participant,
         name='confirm_delete_participant'),

    #  participant deletion route
    path('race/<int:race_id>/delete_participant/<int:participant_id>/delete/', views.delete_participant,
         name='delete_participant'),

    #  endpoint for editing participant data
    path('race/<int:race_id>/participant/<int:participant_id>/edit/', views.edit_participant, name='edit_participant'),

    #  endpoint for linking a users account to a participant instance
    path('link-participant/<int:participant_id>/', views.link_participant, name='link_participant'),

    path('races/<int:race_id>/manage-organisers/', views.manage_organiser_permissions, name='manage_organiser_permissions'),

    path('races/<int:race_id>/organisers/<int:organiser_id>/remove/', views.remove_organiser, name='remove_organiser'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = views.custom_404
handler500 = views.custom_500
handler403 = views.custom_403
