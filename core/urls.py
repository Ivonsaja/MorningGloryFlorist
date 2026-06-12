from django.urls import path
from . import views

urlpatterns = [
    path('admin/laporan/penjualan/', views.admin_laporan_penjualan, name='laporan_penjualan'),
    path('admin/laporan/penjualan/pdf/', views.admin_laporan_penjualan_pdf, name='laporan_penjualan_pdf'),
    path('admin/laporan/produk/', views.laporan_produk, name='laporan_produk'),
    path('admin/laporan/produk/pdf/', views.laporan_produk_pdf, name='laporan_produk_pdf'),
    path('admin/laporan/pelanggan/', views.laporan_pelanggan, name='laporan_pelanggan'),
    path('admin/laporan/pelanggan/pdf/', views.laporan_pelanggan_pdf, name='laporan_pelanggan_pdf'),
]