from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from .models import Kurir, Transaksi, DetailTransaksi
from django.db.models import Q
import os
from django.conf import settings


def kurir_required(view_func):
    """Decorator to ensure kurir is logged in"""
    def wrapper(request, *args, **kwargs):
        if 'kurir_id' not in request.session:
            return redirect('kurir_login')
        try:
            kurir = Kurir.objects.get(idKurir=request.session['kurir_id'])
            request.kurir = kurir
        except Kurir.DoesNotExist:
            del request.session['kurir_id']
            return redirect('kurir_login')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_kurir_or_redirect(request):
    """Helper function to get kurir object or redirect to login"""
    if 'kurir_id' not in request.session:
        return None, redirect('kurir_login')
    try:
        kurir = Kurir.objects.get(idKurir=request.session['kurir_id'])
        return kurir, None
    except Kurir.DoesNotExist:
        del request.session['kurir_id']
        return None, redirect('kurir_login')


def kurir_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        try:
            kurir = Kurir.objects.get(username=username)
            if kurir.check_password(password):
                request.session['kurir_id'] = kurir.idKurir
                return redirect('kurir_dashboard')
            else:
                messages.error(request, 'Username atau password salah')
        except Kurir.DoesNotExist:
            messages.error(request, 'Username atau password salah')
    
    return render(request, 'kurir/login.html')


def kurir_logout(request):
    request.session.flush()
    return redirect('kurir_login')


@kurir_required
def kurir_dashboard(request):
    kurir = request.kurir
    
    # Get transactions assigned to this kurir with status DIKIRIM
    transaksis = Transaksi.objects.filter(
        idKurir=kurir,
        status='DIKIRIM'
    ).select_related('idPelanggan', 'idKurir').prefetch_related('detail_set__idProduk').order_by('-tanggalTransaksi')
    
    # Prepare transaction data for template
    transaksi_data = []
    for i, transaksi in enumerate(transaksis, 1):
        # Format products
        produk_list = []
        for detail in transaksi.detail_set.all():
            produk_nama = detail.idProduk.namaProduk
            produk_jumlah = detail.jumlahProduk
            produk_list.append(f"{produk_nama} ({produk_jumlah})")
        produk_str = ", ".join(produk_list)
        
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        transaksi_data.append({
            'no': i,
            'id': transaksi.idTransaksi,
            'tanggal': transaksi.tanggalTransaksi.strftime('%d/%m/%Y'),
            'pelanggan': transaksi.idPelanggan.namaPelanggan,
            'produk': produk_str,
            'total_akhir': total_akhir,
            'status': transaksi.get_status_display(),
        })
    
    # Get total completed deliveries
    total_selesai = Transaksi.objects.filter(
        idKurir=kurir,
        status='SELESAI'
    ).count()
    
    context = {
        'transaksi_data': transaksi_data,
        'kurir': kurir,
        'total_selesai': total_selesai,
    }
    
    return render(request, 'kurir/dashboard.html', context)


@require_POST
@csrf_protect
@kurir_required
def kurir_update_transaksi(request, transaksi_id):
    kurir = request.kurir
    
    # Get transaction
    transaksi = get_object_or_404(Transaksi, idTransaksi=transaksi_id)
    
    # Check ownership
    if transaksi.idKurir_id != kurir.idKurir:
        return HttpResponseForbidden("Anda tidak memiliki akses ke transaksi ini")
    
    # Check status
    if transaksi.status != 'DIKIRIM':
        messages.error(request, 'Transaksi tidak dalam status yang bisa diupdate')
        return redirect('kurir_dashboard')
    
    # Get form data
    new_status = request.POST.get('status')
    catatan = request.POST.get('catatan', '').strip()
    bukti = request.FILES.get('buktiSampai')
    
    # Validate status
    if new_status not in ['SELESAI', 'DIBATALKAN']:
        messages.error(request, 'Status tidak valid')
        return redirect('kurir_dashboard')
    
    # Validate required fields
    if new_status == 'SELESAI' and not bukti:
        messages.error(request, 'Bukti pengiriman wajib diupload untuk status SELESAI')
        return redirect('kurir_dashboard')
    
    if new_status == 'DIBATALKAN' and not catatan:
        messages.error(request, 'Catatan wajib diisi untuk status DIBATALKAN')
        return redirect('kurir_dashboard')
    
    # Update transaction
    transaksi.status = new_status
    
    if new_status == 'SELESAI':
        transaksi.buktiSampai = bukti
    elif new_status == 'DIBATALKAN':
        transaksi.catatan = catatan
    
    transaksi.save()
    
    messages.success(request, 'Transaksi berhasil diupdate')
    return redirect('kurir_dashboard')