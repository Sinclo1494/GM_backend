"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include

from rest_framework import routers
from api import views
from api.views import (
    pointage_upload_view,
    situation_upload_view,
    TP_AQ_API_View,
    TP_AQ_resume_API_View,
    TP_AE_API_View,
    TP_AE_resume_API_View,
    ValidatePointageView,
    ImportPointageView,
    ValidateGrandMaterielView,
    ImportGrandMaterielView,
    ValidateMarqueView,
    ImportMarqueView,
    ValidateTypeMarqueView,
    ImportTypeMarqueView,
    ValidateSousFamilleView,
    ImportSousFamilleView,
    ValidateSituationAffectationView,
    ImportSituationAffectationView,
    ValidateSiteView,
    ImportSiteView,
    ValidateRegularisationGMView,
    ImportRegularisationGMView,
    )

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


router = routers.DefaultRouter()
router.register(r'grand-materiel', views.GrandMaterielViewSet, 'grand-materiel')
router.register(r'marque-materiel', views.MarqueMaterielViewSet, 'marque-materiel')
router.register(r'type-marque', views.TypeMarqueViewSet, 'type-marque')
router.register(r'sous-famille-materiel', views.SousFamilleMaterielViewSet, 'sous-famille-materiel')
router.register(r'famille-materiel', views.FamilleMaterielViewSet, 'famille-materiel')
router.register(r'categorie-gm', views.CategorieGMViewSet, 'categorie-gm')
router.register(r'type-affectation', views.TypeAffectationViewSet, 'type-affectation')
router.register(r'type-situation', views.TypeSituationViewSet, 'type-situation')
router.register(r'type-etat-materiel', views.TypeEtatMaterielViewSet, 'type-etat-materiel')
router.register(r'situation-materiel', views.SituationMaterielViewSet, 'situation-materiel')
router.register(r'entreprise', views.EntrepriseViewSet, 'entreprise')
router.register(r'filiale', views.FilialeViewSet, 'filiale')
router.register(r'affectation-materiel', views.AffectationMaterielViewSet, 'affectation-materiel')
router.register(r'division', views.DivisionViewSet, 'division')
router.register(r'famille-structures', views.FamilleStructuresViewSet, 'famille-structures')
router.register(r'pointage', views.PointageViewSet, 'pointage')
router.register(r'regularisation-gm', views.RegularisationGMViewSet, 'regularisation-gm')
router.register(r'regularisation-mois-gm2', views.RegularisationMoisGM2ViewSet, 'regularisation-mois-gm2')
router.register(r'site', views.SiteViewSet, 'site')





urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/pointage-validate/', ValidatePointageView.as_view(), name='validate_pointage'),
    path('api/pointage-import/', ImportPointageView.as_view(), name='import_pointage'),
    path('api/gm-validate/', ValidateGrandMaterielView.as_view(), name='validate_gm'),
    path('api/gm-import/', ImportGrandMaterielView.as_view(), name='import_gm'),
    path('api/marque-validate/', ValidateMarqueView.as_view(), name='validate_marque'),
    path('api/marque-import/', ImportMarqueView.as_view(), name='import_marque'),
    path('api/type-marque-validate/', ValidateTypeMarqueView.as_view(), name='validate_type_marque'),
    path('api/type-marque-import/', ImportTypeMarqueView.as_view(), name='import_type_marque'),
    path('api/sous-famille-validate/', ValidateSousFamilleView.as_view(), name='validate_sous_famille'),
    path('api/sous-famille-import/', ImportSousFamilleView.as_view(), name='import_sous_famille'),
    path('api/situation-affectation-validate/', ValidateSituationAffectationView.as_view(), name='validate_situation_affectation'),
    path('api/situation-affectation-import/', ImportSituationAffectationView.as_view(), name='import_situation_affectation'),
    path('api/site-validate/', ValidateSiteView.as_view(), name='validate_site'),
    path('api/site-import/', ImportSiteView.as_view(), name='import_site'),
    path('api/regularisation-gm-validate/', ValidateRegularisationGMView.as_view(), name='validate_regularisation_gm'),
    path('api/regularisation-gm-import/', ImportRegularisationGMView.as_view(), name='import_regularisation_gm'),
    path('api/pointage-upload/', pointage_upload_view),
    path('api/situation-upload/', situation_upload_view),
    path('api/aqtp/', TP_AQ_API_View.as_view()),
    path('api/aqtpr/', TP_AQ_resume_API_View.as_view()),
    path('api/aetp/', TP_AE_API_View.as_view()),
    path('api/aetpr/', TP_AE_resume_API_View.as_view()),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
