from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.template.loader import get_template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from datetime import datetime
from .models import Transaksi, Produk, Pelanggan, Kurir
from django.db.models import Sum, Q, Count, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal
from io import BytesIO
from xhtml2pdf import pisa
import os
from pathlib import Path
import django
from django.conf import settings as django_settings

def build_laporan_penjualan_queryset(request):
    # Get filter parameters
    status = request.GET.get('status', '')
    kurir_id = request.GET.get('kurir', '') # Ambil filter kurir
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Build queryset
    queryset = Transaksi.objects.select_related('idPelanggan', 'idKurir').prefetch_related('detail_set__idProduk').order_by('-tanggalTransaksi')
    
    # Apply filters
    if status:
        queryset = queryset.filter(status=status)
    
    if kurir_id:
        queryset = queryset.filter(idKurir_id=kurir_id)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            start_dt = timezone.make_aware(start_dt)
            queryset = queryset.filter(tanggalTransaksi__date__gte=start_dt.date())
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = timezone.make_aware(end_dt)
            queryset = queryset.filter(tanggalTransaksi__date__lte=end_dt.date())
        except ValueError:
            pass
    
    # Prepare context
    context_filters = {
        'status': status,
        'kurir': kurir_id,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # Calculate summary
    total_transaksi = queryset.count()
    
    # Calculate total pendapatan (only for non-DIBATALKAN status)
    total_pendapatan = 0
    for transaksi in queryset:
        if transaksi.status != 'DIBATALKAN':
            total_pendapatan += float(transaksi.totalTransaksi) + float(transaksi.ongkir)
    
    summary = {
        'total_transaksi': total_transaksi,
        'total_pendapatan': total_pendapatan,
    }
    
    return queryset, context_filters, summary


@staff_member_required
def admin_laporan_penjualan(request):
    queryset, context_filters, summary = build_laporan_penjualan_queryset(request)
    
    # Prepare data for template
    transaksi_data = []
    for i, transaksi in enumerate(queryset, 1):
        # Ambil list item detail untuk dikirim utuh ke template
        items = []
        for detail in transaksi.detail_set.all():
            items.append({
                'nama_produk': detail.idProduk.namaProduk,
                'jumlah': detail.jumlahProduk,
                'harga_satuan': detail.hargaSatuanSaatTransaksi or detail.idProduk.hargaProduk,
                'subtotal_item': detail.subTotal,
            })
            
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        transaksi_data.append({
            'no': i,
            'tanggal': transaksi.tanggalTransaksi.strftime('%d/%m/%Y'),
            'pelanggan': transaksi.idPelanggan.namaPelanggan,
            'nama_kurir': transaksi.idKurir.namaKurir if transaksi.idKurir else "Belum Ditentukan",
            'items': items,
            'sub_total_transaksi': transaksi.totalTransaksi, # Total produk sebelum ongkir
            'ongkir': transaksi.ongkir,
            'total_akhir': total_akhir,
            'status': transaksi.get_status_display(),
        })
    
    context = {
        'transaksi_data': transaksi_data,
        'filters': context_filters,
        'summary': summary,
        'status_choices': Transaksi.STATUS_CHOICES,
        'kurir_choices': Kurir.objects.all(), # Kirim data kurir untuk dropdown
    }
    
    return render(request, 'admin/laporan_penjualan.html', context)


@staff_member_required
def admin_laporan_penjualan_pdf(request):
    queryset, context_filters, summary = build_laporan_penjualan_queryset(request)
    
    # Prepare data for template
    transaksi_data = []
    for i, transaksi in enumerate(queryset, 1):
        # Ambil list item detail untuk dikirim utuh ke template
        items = []
        for detail in transaksi.detail_set.all():
            items.append({
                'nama_produk': detail.idProduk.namaProduk,
                'jumlah': detail.jumlahProduk,
                'harga_satuan': detail.hargaSatuanSaatTransaksi or detail.idProduk.hargaProduk,
                'subtotal_item': detail.subTotal,
            })
            
        total_akhir = float(transaksi.totalTransaksi) + float(transaksi.ongkir)
        
        transaksi_data.append({
            'no': i,
            'tanggal': transaksi.tanggalTransaksi.strftime('%d/%m/%Y'),
            'pelanggan': transaksi.idPelanggan.namaPelanggan,
            'nama_kurir': transaksi.idKurir.namaKurir if transaksi.idKurir else "Belum Ditentukan",
            'items': items,
            'sub_total_transaksi': transaksi.totalTransaksi, # Total produk sebelum ongkir
            'ongkir': transaksi.ongkir,
            'total_akhir': total_akhir,
            'status': transaksi.get_status_display(),
        })
        
    kurir_nama = ""
    if context_filters.get('kurir'):
        try:
            kurir_obj = Kurir.objects.get(idKurir=context_filters['kurir'])
            kurir_nama = kurir_obj.namaKurir
        except Kurir.DoesNotExist:
            pass
    
    context = {
        'transaksi_data': transaksi_data,
        'filters': context_filters,
        'kurir_nama': kurir_nama,
        'summary': summary,
        'status_choices': Transaksi.STATUS_CHOICES,
        'today': timezone.now().strftime('%d/%m/%Y'),
    }
    
    template_path = 'admin/laporan_penjualan_pdf.html'
    template = get_template(template_path)
    html = template.render(context)
    
    # Create a PDF
    buffer = BytesIO()
    
    # Define link callback for static files
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        
        # Handle static files
        if uri.startswith('/static/'):
            # Convert /static/... to the actual static file path
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path):
                    return path
            # If not found in STATICFILES_DIRS, try STATIC_ROOT
            path = os.path.join(str(settings.STATIC_ROOT), static_path)
            return path
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
            return path
        return uri
    
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8', link_callback=link_callback)
    
    # If error then show some funy view
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    
    # Return PDF response
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_penjualan.pdf"'
    
    return response


def build_laporan_produk_queryset(request):
    status = request.GET.get('status', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    transaksi_filter = Q(detailtransaksi__idTransaksi__status__in=[
    'MENUNGGU_VERIFIKASI', 'DISETUJUI', 'DIKIRIM', 'SELESAI', 'REFUND_SELESAI'
    ])

    if status:
        transaksi_filter = Q(detailtransaksi__idTransaksi__status=status)

    if start_date:
        try:
            sd = datetime.strptime(start_date, '%Y-%m-%d').date()
            transaksi_filter &= Q(detailtransaksi__idTransaksi__tanggalTransaksi__date__gte=sd)
        except ValueError:
            pass

    if end_date:
        try:
            ed = datetime.strptime(end_date, '%Y-%m-%d').date()
            transaksi_filter &= Q(detailtransaksi__idTransaksi__tanggalTransaksi__date__lte=ed)
        except ValueError:
            pass

    qs = Produk.objects.all().annotate(
        kuantitas_terjual=Coalesce(
            Sum('detailtransaksi__jumlahProduk', filter=transaksi_filter),
            0
        )
    ).order_by('namaProduk')

    filters = {
        'status': status,
        'start_date': start_date,
        'end_date': end_date,
    }

    return qs, filters


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_produk(request):
    qs, filters = build_laporan_produk_queryset(request)

    produk_data = []
    for i, p in enumerate(qs, 1):
        produk_data.append({
            'no': i,
            'nama': p.namaProduk,
            'harga': p.hargaProduk,
            'stok': p.stok,
            'terjual': p.kuantitas_terjual,
        })

    context = {
        'produk_data': produk_data,
        'filters': filters,
       
    }
    return render(request, 'admin/laporan_produk.html', context)


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_produk_pdf(request):
    qs, filters = build_laporan_produk_queryset(request)

    produk_data = []
    for i, p in enumerate(qs, 1):
        produk_data.append({
            'no': i,
            'nama': p.namaProduk,
            'harga': p.hargaProduk,
            'stok': p.stok,
            'terjual': p.kuantitas_terjual,
        })

    context = {
        'produk_data': produk_data,
        'filters': filters,
        'today': timezone.now().strftime('%d/%m/%Y'),
    }

    template = get_template('admin/laporan_produk_pdf.html')
    html = template.render(context)

    buffer = BytesIO()
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        
        if uri.startswith('/static/'):
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path):
                    return path
            path = os.path.join(str(settings.STATIC_ROOT), static_path)
            return path
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
            return path
        return uri
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8', link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_produk.pdf"'
    return response


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_pelanggan(request):
    # Ambil data pelanggan langsung berdasarkan urutan nama
    pelanggan_qs = Pelanggan.objects.all().order_by('namaPelanggan')

    # Petakan atribut model dasar ke template data
    pelanggan_data = []
    for i, pelanggan in enumerate(pelanggan_qs, 1):
        pelanggan_data.append({
            'no': i,
            'nama': pelanggan.namaPelanggan,
            'username': pelanggan.username,
            'alamat': pelanggan.alamat or '-',
            'nomor_telepon': pelanggan.nomorTelepon or '-',
        })

    context = {
        'pelanggan_data': pelanggan_data,
    }
    return render(request, 'admin/laporan_pelanggan.html', context)


@login_required
@permission_required('auth.view_user', raise_exception=True)
def laporan_pelanggan_pdf(request):
    pelanggan_qs = Pelanggan.objects.all().order_by('namaPelanggan')

    pelanggan_data = []
    for i, pelanggan in enumerate(pelanggan_qs, 1):
        pelanggan_data.append({
            'no': i,
            'nama': pelanggan.namaPelanggan,
            'username': pelanggan.username,
            'alamat': pelanggan.alamat or '-',
            'nomor_telepon': pelanggan.nomorTelepon or '-',
        })

    context = {
        'pelanggan_data': pelanggan_data,
        'today': timezone.now().strftime('%d/%m/%Y'),
        'summary': {
            'total_pelanggan': len(pelanggan_data),
        }
    }

    template = get_template('admin/laporan_pelanggan_pdf.html')
    html = template.render(context)

    buffer = BytesIO()
    
    def link_callback(uri, rel):
        import os
        from django.conf import settings
        if uri.startswith('/static/'):
            static_path = uri.replace('/static/', '').lstrip('/')
            for static_dir in settings.STATICFILES_DIRS:
                path = os.path.join(str(static_dir), static_path)
                if os.path.exists(path): return path
            return os.path.join(str(settings.STATIC_ROOT), static_path)
        elif uri.startswith(settings.MEDIA_URL):
            return os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, '', 1))
        return uri
    
    pisa_status = pisa.CreatePDF(html, dest=buffer, encoding='utf-8', link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="laporan_pelanggan.pdf"'
    return response
