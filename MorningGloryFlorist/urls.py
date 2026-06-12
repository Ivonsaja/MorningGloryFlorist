from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', include('core.urls')),
    path('kurir/', include('core.urls_kurir')),
    path('', include('core.urls_pelanggan')),
    path('admin/', admin.site.urls),
]

# Serve media & static files — aktif saat DEBUG=True (development/testing)
# Di PythonAnywhere (DEBUG=False), file-file ini di-serve langsung oleh
# konfigurasi "Static files" di Web Tab, bukan oleh Django.
# Baris ini tetap aman dibiarkan karena tidak berpengaruh saat DEBUG=False.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Saat DEBUG=False di PythonAnywhere, media tetap perlu di-route oleh Django
    # jika belum dikonfigurasi di Web Tab — aktifkan baris di bawah ini
    # HANYA jika Anda belum set mapping di Static files Web Tab:
    # urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    pass
