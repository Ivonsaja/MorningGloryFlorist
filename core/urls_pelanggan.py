from django.urls import path
from . import views_pelanggan

urlpatterns = [
    path('', views_pelanggan.pelanggan_index, name='pelanggan_index'),
    path('katalog/', views_pelanggan.pelanggan_katalog, name='pelanggan_katalog'),
    path('produk/<int:idProduk>/', views_pelanggan.pelanggan_produk_detail, name='pelanggan_produk_detail'),
    path('cara-pesan/', views_pelanggan.pelanggan_cara_pesan, name='pelanggan_cara_pesan'),
    path('kontak/', views_pelanggan.pelanggan_kontak, name='pelanggan_kontak'),
    
    path('pelanggan/register/', views_pelanggan.pelanggan_register, name='pelanggan_register'),
    path('pelanggan/login/', views_pelanggan.pelanggan_login, name='pelanggan_login'),
    path('pelanggan/logout/', views_pelanggan.pelanggan_logout, name='pelanggan_logout'),
    path('pelanggan/password/', views_pelanggan.pelanggan_password, name='pelanggan_password'),
    
    path('keranjang/', views_pelanggan.pelanggan_cart, name='pelanggan_cart'),
    path('keranjang/tambah/<int:idProduk>/', views_pelanggan.pelanggan_cart_add, name='pelanggan_cart_add'),
    path('keranjang/update/<int:idProduk>/', views_pelanggan.pelanggan_cart_update, name='pelanggan_cart_update'),
    path('keranjang/hapus/<int:idProduk>/', views_pelanggan.pelanggan_cart_remove, name='pelanggan_cart_remove'),
    
    path('checkout/', views_pelanggan.pelanggan_checkout, name='pelanggan_checkout'),
    path('checkout/sukses/<int:idTransaksi>/', views_pelanggan.pelanggan_checkout_sukses, name='pelanggan_checkout_sukses'),
    
    path('pesanan/', views_pelanggan.pelanggan_pesanan_list, name='pelanggan_pesanan_list'),
    path('pesanan/<int:idTransaksi>/', views_pelanggan.pelanggan_pesanan_detail, name='pelanggan_pesanan_detail'),
    
    path('akun/', views_pelanggan.pelanggan_akun, name='pelanggan_akun'),
]