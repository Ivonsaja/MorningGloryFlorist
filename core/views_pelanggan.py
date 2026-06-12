from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Pelanggan, Produk, Transaksi, DetailTransaksi
from django.conf import settings
import os


def pelanggan_required(view_func):
    """Decorator to ensure pelanggan is logged in"""
    def wrapper(request, *args, **kwargs):
        if 'pelanggan_id' not in request.session:
            next_url = request.path
            return redirect(f'/pelanggan/login/?next={next_url}')
        try:
            pelanggan = Pelanggan.objects.get(idPelanggan=request.session['pelanggan_id'])
            request.pelanggan = pelanggan
        except Pelanggan.DoesNotExist:
            del request.session['pelanggan_id']
            return redirect('pelanggan_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def pelanggan_index(request):
    products = Produk.objects.all()[:6]
    context = {'products': products}
    return render(request, 'pelanggan/index.html', context)


def pelanggan_katalog(request):
    products = Produk.objects.all().order_by('namaProduk')
    context = {'products': products}
    return render(request, 'pelanggan/katalog.html', context)


def pelanggan_produk_detail(request, idProduk):
    product = get_object_or_404(Produk, idProduk=idProduk)
    context = {'product': product}
    return render(request, 'pelanggan/produk_detail.html', context)


def pelanggan_cara_pesan(request):
    context = {
        'is_logged_in': bool(request.session.get('pelanggan_id')),
        'cart_count': sum(request.session.get('cart', {}).values()) if request.session.get('cart') else 0,
    }
    return render(request, 'pelanggan/cara_pesan.html', context)


def pelanggan_kontak(request):
    return render(request, 'pelanggan/kontak.html')


def pelanggan_register(request):
    if request.method == 'POST':
        nama_pelanggan = request.POST.get('namaPelanggan', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        alamat = request.POST.get('alamat', '').strip()
        nomor_telepon = request.POST.get('nomorTelepon', '').strip()
        
        old_data = {
            'namaPelanggan': nama_pelanggan,
            'username': username,
            'alamat': alamat,
            'nomorTelepon': nomor_telepon
        }
        
        if not username or not password or not nama_pelanggan:
            return render(request, 'pelanggan/register.html', {
                'error': 'Nama pelanggan, username, dan password wajib diisi',
                'old': old_data
            })
        
        if password != confirm_password:
            return render(request, 'pelanggan/register.html', {
                'error': 'Password tidak cocok',
                'old': old_data
            })
        
        if Pelanggan.objects.filter(username=username).exists():
            return render(request, 'pelanggan/register.html', {
                'error': 'Username sudah digunakan',
                'old': old_data
            })
        
        try:
            pelanggan = Pelanggan(
                namaPelanggan=nama_pelanggan,
                username=username,
                alamat=alamat,
                nomorTelepon=nomor_telepon
            )
            pelanggan.set_password(password)
            pelanggan.save()
            
            request.session['pelanggan_id'] = pelanggan.idPelanggan
            messages.success(request, 'Registrasi berhasil!')
            return redirect('pelanggan_index')
        except Exception as e:
            return render(request, 'pelanggan/register.html', {
                'error': f'Terjadi kesalahan: {str(e)}',
                'old': old_data
            })
    
    return render(request, 'pelanggan/register.html')


def pelanggan_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        next_url = request.POST.get('next') or request.GET.get('next') or '/'
        
        if not username or not password:
            return render(request, 'pelanggan/login.html', {
                'error': 'Username dan password wajib diisi',
                'username': username
            })
        
        try:
            pelanggan = Pelanggan.objects.get(username=username)
            if pelanggan.check_password(password):
                request.session['pelanggan_id'] = pelanggan.idPelanggan
                messages.success(request, 'Login berhasil!')
                return redirect(next_url if next_url != '/pelanggan/login/' else 'pelanggan_index')
            else:
                return render(request, 'pelanggan/login.html', {
                    'error': 'Username atau password salah',
                    'username': username
                })
        except Pelanggan.DoesNotExist:
            return render(request, 'pelanggan/login.html', {
                'error': 'Username atau password salah',
                'username': username
            })
    
    return render(request, 'pelanggan/login.html')


def pelanggan_logout(request):
    if 'pelanggan_id' in request.session:
        del request.session['pelanggan_id']
    messages.success(request, 'Anda telah logout')
    return redirect('pelanggan_index')


@pelanggan_required
def pelanggan_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_new_password = request.POST.get('confirm_new_password', '')
        
        pelanggan = request.pelanggan
        
        if not pelanggan.check_password(old_password):
            messages.error(request, 'Password lama salah')
            return render(request, 'pelanggan/password.html')
        
        if new_password != confirm_new_password:
            messages.error(request, 'Password baru tidak cocok')
            return render(request, 'pelanggan/password.html')
        
        try:
            pelanggan.set_password(new_password)
            pelanggan.save()
            messages.success(request, 'Password berhasil diubah')
            return redirect('pelanggan_akun')
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return render(request, 'pelanggan/password.html')


def get_cart(request):
    cart = request.session.get('cart', {})
    return cart


def update_cart_item(cart, idProduk, qty):
    if qty <= 0:
        if str(idProduk) in cart:
            del cart[str(idProduk)]
    else:
        cart[str(idProduk)] = qty


@pelanggan_required
def pelanggan_cart(request):
    cart = get_cart(request)
    cart_items = []
    total = 0
    
    for idProduk, qty in cart.items():
        try:
            product = Produk.objects.get(idProduk=idProduk)
            subtotal = float(product.hargaProduk) * qty
            total += subtotal
            cart_items.append({
                'product': product,
                'qty': qty,
                'subtotal': subtotal
            })
        except Produk.DoesNotExist:
            continue
    
    context = {'cart_items': cart_items, 'total': total}
    return render(request, 'pelanggan/cart.html', context)


@pelanggan_required
@require_POST
@csrf_protect
def pelanggan_cart_add(request, idProduk):
    qty = int(request.POST.get('qty', 1))
    
    try:
        product = Produk.objects.get(idProduk=idProduk)
        
        if qty < 1:
            messages.error(request, 'Kuantitas minimal adalah 1')
            return redirect('pelanggan_produk_detail', idProduk=idProduk)
        
        if product.stok < qty:
            messages.error(request, f'Stok tidak mencukupi. Tersedia: {product.stok}')
            return redirect('pelanggan_produk_detail', idProduk=idProduk)
        
        cart = get_cart(request)
        current_qty = int(cart.get(str(idProduk), 0))
        new_qty = current_qty + qty
        
        if product.stok < new_qty:
            messages.error(request, f'Stok tidak mencukupi untuk ditambahkan. Tersedia: {product.stok}')
            return redirect('pelanggan_cart')
        
        update_cart_item(cart, idProduk, new_qty)
        request.session['cart'] = cart
        messages.success(request, 'Produk berhasil ditambahkan ke keranjang')
        
    except Produk.DoesNotExist:
        messages.error(request, 'Produk tidak ditemukan')
    
    return redirect('pelanggan_cart')


@pelanggan_required
@require_POST
@csrf_protect
def pelanggan_cart_update(request, idProduk):
    qty = int(request.POST.get('qty', 1))
    
    try:
        product = Produk.objects.get(idProduk=idProduk)
        
        if qty < 1:
            qty = 1
        
        if product.stok < qty:
            messages.error(request, f'Stok tidak mencukupi. Tersedia: {product.stok}')
            return redirect('pelanggan_cart')
        
        cart = get_cart(request)
        update_cart_item(cart, idProduk, qty)
        request.session['cart'] = cart
        messages.success(request, 'Keranjang berhasil diupdate')
        
    except Produk.DoesNotExist:
        messages.error(request, 'Produk tidak ditemukan')
    
    return redirect('pelanggan_cart')


@pelanggan_required
@require_POST
@csrf_protect
def pelanggan_cart_remove(request, idProduk):
    cart = get_cart(request)
    
    if str(idProduk) in cart:
        del cart[str(idProduk)]
        request.session['cart'] = cart
        messages.success(request, 'Produk dihapus dari keranjang')
    
    return redirect('pelanggan_cart')


@pelanggan_required
def pelanggan_checkout(request):
    cart = get_cart(request)
    
    if not cart:
        messages.error(request, 'Keranjang kosong')
        return redirect('pelanggan_cart')
    
    cart_items = []
    total_transaksi = 0
    
    for idProduk, qty in cart.items():
        try:
            product = Produk.objects.get(idProduk=idProduk)
            if product.stok < qty:
                messages.error(request, f'Stok {product.namaProduk} tidak mencukupi')
                return redirect('pelanggan_cart')
            
            subtotal = float(product.hargaProduk) * qty
            total_transaksi += subtotal
            cart_items.append({
                'product': product,
                'qty': qty,
                'subtotal': subtotal
            })
        except Produk.DoesNotExist:
            continue
    
    if request.method == 'POST':
        alamat_pengiriman = request.POST.get('alamatPengiriman', '').strip()
        catatan = request.POST.get('catatan', '').strip()
        bukti_bayar = request.FILES.get('buktiBayar')
        
        if not alamat_pengiriman:
            messages.error(request, 'Alamat pengiriman wajib diisi')
            return render(request, 'pelanggan/checkout.html', {'cart_items': cart_items, 'total_transaksi': total_transaksi})
        
        if not bukti_bayar:
            messages.error(request, 'Bukti pembayaran wajib diupload')
            return render(request, 'pelanggan/checkout.html', {'cart_items': cart_items, 'total_transaksi': total_transaksi})
        
        pelanggan = request.pelanggan
        
        try:
            with transaction.atomic():
                transaksi = Transaksi(
                    idPelanggan=pelanggan,
                    alamatPengiriman=alamat_pengiriman,
                    catatan=catatan,
                    buktiBayar=bukti_bayar,
                    status='MENUNGGU_VERIFIKASI'
                )
                transaksi.full_clean()
                transaksi.save()
                
                for item in cart_items:
                    product = item['product']
                    qty = item['qty']
                    
                    detail = DetailTransaksi(
                        idTransaksi=transaksi,
                        idProduk=product,
                        jumlahProduk=qty
                    )
                    detail.save()
                    
                    product.stok -= qty
                    product.save()
                
                del request.session['cart']
                
                messages.success(request, 'Pesanan berhasil dibuat!')
                return redirect('pelanggan_checkout_sukses', idTransaksi=transaksi.idTransaksi)
                
        except ValidationError as e:
            messages.error(request, f'Validasi gagal: {str(e)}')
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    return render(request, 'pelanggan/checkout.html', {'cart_items': cart_items, 'total_transaksi': total_transaksi})


@pelanggan_required
def pelanggan_checkout_sukses(request, idTransaksi):
    transaksi = get_object_or_404(Transaksi, idTransaksi=idTransaksi)
    
    if transaksi.idPelanggan != request.pelanggan:
        return redirect('pelanggan_pesanan_list')
    
    context = {'transaksi': transaksi}
    return render(request, 'pelanggan/checkout_sukses.html', context)


@pelanggan_required
def pelanggan_pesanan_list(request):
    transaksis = Transaksi.objects.filter(
        idPelanggan=request.pelanggan
    ).order_by('-tanggalTransaksi')
    
    pesanan_data = []
    for transaksi in transaksis:
        total_produk = sum(detail.jumlahProduk for detail in transaksi.detail_set.all())
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        pesanan_data.append({
            'transaksi': transaksi,
            'total_produk': total_produk,
            'total_akhir': total_akhir
        })
    
    context = {'pesanan_data': pesanan_data}
    return render(request, 'pelanggan/pesanan_list.html', context)


@pelanggan_required
def pelanggan_pesanan_detail(request, idTransaksi):
    transaksi = get_object_or_404(Transaksi, idTransaksi=idTransaksi)
    
    if transaksi.idPelanggan != request.pelanggan:
        messages.error(request, 'Pesanan tidak ditemukan')
        return redirect('pelanggan_pesanan_list')
    
    details = transaksi.detail_set.all()
    total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
    
    context = {
        'transaksi': transaksi,
        'details': details,
        'total_akhir': total_akhir
    }
    return render(request, 'pelanggan/pesanan_detail.html', context)


@pelanggan_required
def pelanggan_akun(request):
    pelanggan = request.pelanggan
    
    if request.method == 'POST':
        nama_pelanggan = request.POST.get('namaPelanggan', '').strip()
        alamat = request.POST.get('alamat', '').strip()
        nomor_telepon = request.POST.get('nomorTelepon', '').strip()
        
        if not nama_pelanggan:
            messages.error(request, 'Nama pelanggan wajib diisi')
            return render(request, 'pelanggan/akun.html')
        
        try:
            pelanggan.namaPelanggan = nama_pelanggan
            pelanggan.alamat = alamat
            pelanggan.nomorTelepon = nomor_telepon
            pelanggan.save()
            messages.success(request, 'Profil berhasil diupdate')
        except Exception as e:
            messages.error(request, f'Terjadi kesalahan: {str(e)}')
    
    context = {'pelanggan': pelanggan}
    return render(request, 'pelanggan/akun.html', context)
