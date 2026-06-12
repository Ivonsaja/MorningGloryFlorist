from django.contrib import admin
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db import transaction
from django.contrib import messages
from .models import Pelanggan, Produk, Transaksi, DetailTransaksi, Kurir
from django.contrib.humanize.templatetags.humanize import intcomma
class DetailTransaksiInline(admin.StackedInline):
    model = DetailTransaksi
    extra = 0
    fields = ('idProduk', 'jumlahProduk', 'subTotal')
    readonly_fields = ('subTotal',)
    autocomplete_fields = ('idProduk',)
    verbose_name = "Detail Produk"
    verbose_name_plural = "Detail Produk"

class KurirAdmin(admin.ModelAdmin):
    list_display = ('namaKurir', 'noHp', 'username', 'aksi_kurir')
    search_fields = ('namaKurir', 'username', 'noHp')
    fieldsets = (
        (None, {
            'fields': ('namaKurir', 'noHp', 'username')
        }),
        ('Password', {
            'fields': ('passwordHash',),
            'description': 'Masukkan password untuk kurir. Password akan di-hash secara otomatis saat disimpan.'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        # Hash password if it's plain text (not starting with pbkdf2_)
        if obj.passwordHash and not obj.passwordHash.startswith('pbkdf2_'):
            obj.set_password(obj.passwordHash)
        super().save_model(request, obj, form, change)
    
    def aksi_kurir(self, obj):
        change_url = reverse('admin:core_kurir_change', args=[obj.pk])
        delete_url = reverse('admin:core_kurir_delete', args=[obj.pk])
        
        buttons = [
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="View/Edit">'
            f'<i class="fa-solid fa-eye"></i></a>',
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="Edit">'
            f'<i class="fa-solid fa-pen-to-square"></i></a>'
        ]
        
        # Add delete button if user has permission and request exists
        if hasattr(self, '_request') and self._request and self.has_delete_permission(self._request, obj):
            buttons.append(
                f'<a href="{delete_url}" class="btn btn-sm" style="color: #dc3545;" title="Delete">'
                f'<i class="fa-solid fa-trash"></i></a>'
            )
        
        return mark_safe(''.join(buttons))
    
    aksi_kurir.short_description = "Aksi"
    
    def get_queryset(self, request):
        self._request = request
        return super().get_queryset(request)
    
    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

class ProdukAdmin(admin.ModelAdmin):
    list_display = ('namaProduk', 'Harga', 'stok', 'aksi_produk')
    search_fields = ('namaProduk',)
    ordering = ('namaProduk',)
    list_filter = ('stok',)
    
    def aksi_produk(self, obj):
        change_url = reverse('admin:core_produk_change', args=[obj.idProduk])
        delete_url = reverse('admin:core_produk_delete', args=[obj.idProduk])
        
        buttons = [
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="View/Edit">'
            f'<i class="fa-solid fa-eye"></i></a>',
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="Edit">'
            f'<i class="fa-solid fa-pen-to-square"></i></a>'
        ]
        
        # Add delete button if user has permission and request exists
        if hasattr(self, '_request') and self._request and self.has_delete_permission(self._request, obj):
            buttons.append(
                f'<a href="{delete_url}" class="btn btn-sm" style="color: #dc3545;" title="Delete">'
                f'<i class="fa-solid fa-trash"></i></a>'
            )
        
        return mark_safe(''.join(buttons))
    
    aksi_produk.short_description = "Aksi"
    @admin.display(description='Harga Produk')
    def Harga(self, obj):
        return f'Rp. {intcomma(obj.hargaProduk)}'

    Harga.short_description = 'Harga Produk'
    def get_queryset(self, request):
        self._request = request
        return super().get_queryset(request)
    
    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

class PelangganAdmin(admin.ModelAdmin):
    list_display = ('namaPelanggan', 'username', 'alamat', 'nomorTelepon', 'aksi_pelanggan')
    search_fields = ('namaPelanggan', 'username')
    
    def save_model(self, request, obj, form, change):
        if change:
            old_obj = Pelanggan.objects.get(pk=obj.pk)
            if obj.passwordHash != old_obj.passwordHash:
                obj.set_password(obj.passwordHash)
        else:
            obj.set_password(obj.passwordHash)
        super().save_model(request, obj, form, change)
    
    def aksi_pelanggan(self, obj):
        change_url = reverse('admin:core_pelanggan_change', args=[obj.pk])
        delete_url = reverse('admin:core_pelanggan_delete', args=[obj.pk])
        
        buttons = [
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="View/Edit">'
            f'<i class="fa-solid fa-eye"></i></a>',
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="Edit">'
            f'<i class="fa-solid fa-pen-to-square"></i></a>'
        ]
        
        # Add delete button if user has permission and request exists
        if hasattr(self, '_request') and self._request and self.has_delete_permission(self._request, obj):
            buttons.append(
                f'<a href="{delete_url}" class="btn btn-sm" style="color: #dc3545;" title="Delete">'
                f'<i class="fa-solid fa-trash"></i></a>'
            )
        
        return mark_safe(''.join(buttons))
    
    aksi_pelanggan.short_description = "Aksi"

def set_disetujui(modeladmin, request, queryset):
    for transaksi in queryset:
        try:
            transaksi.set_status('DISETUJUI')
        except ValidationError as e:
            modeladmin.message_user(request, f"Error pada transaksi {transaksi.idTransaksi}: {e}", level='error')
set_disetujui.short_description = "Set status Disetujui"

def set_dikirim(modeladmin, request, queryset):
    for transaksi in queryset:
        try:
            transaksi.set_status('DIKIRIM')
        except ValidationError as e:
            modeladmin.message_user(request, f"Error pada transaksi {transaksi.idTransaksi}: {e}", level='error')
set_dikirim.short_description = "Set status Dikirim"

def set_selesai(modeladmin, request, queryset):
    for transaksi in queryset:
        try:
            transaksi.set_status('SELESAI')
        except ValidationError as e:
            modeladmin.message_user(request, f"Error pada transaksi {transaksi.idTransaksi}: {e}", level='error')
set_selesai.short_description = "Set status Selesai"

def set_dibatalkan(modeladmin, request, queryset):
    for transaksi in queryset:
        try:
            transaksi.set_status('DIBATALKAN')
        except ValidationError as e:
            modeladmin.message_user(request, f"Error pada transaksi {transaksi.idTransaksi}: {e}", level='error')
set_dibatalkan.short_description = "Set status Dibatalkan"

def set_refund_selesai(modeladmin, request, queryset):
    for transaksi in queryset:
        try:
            transaksi.set_status('REFUND_SELESAI')
        except ValidationError as e:
            modeladmin.message_user(request, f"Error pada transaksi {transaksi.idTransaksi}: {e}", level='error')
set_refund_selesai.short_description = "Set status Refund Selesai"

class TransaksiAdmin(admin.ModelAdmin):
    list_display = ('tanggalTransaksi', 'idPelanggan', 'status', 'TotalTransaksi', 'thumb_bukti_bayar', 'thumb_bukti_refund', 'aksi')
    list_filter = ('status', 'tanggalTransaksi')
    search_fields = ('idTransaksi', 'idPelanggan__namaPelanggan', 'idPelanggan__username')
    date_hierarchy = 'tanggalTransaksi'
    ordering = ('-tanggalTransaksi',)
    readonly_fields = ('totalTransaksi', 'tanggalTransaksi', 'tanggalVerifikasi')
    inlines = [DetailTransaksiInline]
    actions = [set_disetujui, set_dikirim, set_selesai, set_dibatalkan, set_refund_selesai]
    fieldsets = (
        ('Pelanggan & Pengiriman', {
            'fields': ('idPelanggan', 'idKurir', 'alamatPengiriman', 'ongkir')
        }),
        ('Status & Catatan', {
            'fields': ('status', 'catatan')
        }),
        ('Pembayaran', {
            'fields': ('buktiBayar',)
        }),
        ('Pengiriman', {
            'fields': ('buktiSampai',)
        }),
        ('Refund', {
            'fields': ('bankRefund', 'rekeningRefund', 'buktiRefund', 'tanggalRefund', 'catatanRefund')
        }),
        ('Ringkasan', {
            'fields': ('tanggalTransaksi', 'totalTransaksi')
        }),
    )
    
    @admin.display(description='Total Pembayaran')
    def TotalTransaksi(self, obj):
        return f'Rp. {intcomma(obj.totalTransaksi)}'

    def save_model(self, request, obj, form, change):
        # Validate kurir required for DIKIRIM status
        if obj.status == 'DIKIRIM' and not obj.idKurir:
            from django.core.exceptions import ValidationError
            raise ValidationError("Kurir wajib dipilih sebelum status DIKIRIM")
        
        # Auto-complete status when kurir uploads proof of delivery
        if change:
            old_obj = Transaksi.objects.get(pk=obj.pk)
            old_status = old_obj.status
            if old_status == 'DIKIRIM' and obj.buktiSampai and obj.status == 'DIKIRIM':
                obj.status = 'SELESAI'
        
        if change:  # Edit transaction
            # Get old status from database
            old_obj = Transaksi.objects.get(pk=obj.pk)
            old_status = old_obj.status
            new_status = obj.status
            
            # Restore stock if status changed to DIBATALKAN
            if old_status != 'DIBATALKAN' and new_status == 'DIBATALKAN':
                with transaction.atomic():
                    # Restore stock from all details
                    for detail in obj.detail_set.all():
                        produk = detail.idProduk
                        produk.stok += detail.jumlahProduk
                        produk.save()
                    
                    # Save the transaction
                    super().save_model(request, obj, form, change)
                    
                    # Show success message
                    messages.success(request, f"Stok berhasil dikembalikan untuk transaksi {obj.idTransaksi}")
                    return
        
        # For new transactions or non-cancellation status changes, save normally
        super().save_model(request, obj, form, change)
    
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        
        # Only process stock deduction for new transactions
        if not change:  # New transaction (add)
            obj = form.instance
            active_statuses = ['MENUNGGU_VERIFIKASI', 'DISETUJUI', 'DIKIRIM', 'SELESAI']
            
            if obj.status in active_statuses and obj.detail_set.exists():
                # Calculate total first
                obj.update_total()
                
                # Deduct stock
                for detail in obj.detail_set.all():
                    produk = detail.idProduk
                    if produk.stok < detail.jumlahProduk:
                        from django.core.exceptions import ValidationError
                        raise ValidationError(f"Stok {produk.namaProduk} tidak mencukupi. Tersedia: {produk.stok}, Dibutuhkan: {detail.jumlahProduk}")
                    produk.stok -= detail.jumlahProduk
                    produk.save()
    
    def thumb_bukti_bayar(self, obj):
        if obj.buktiBayar:
            return mark_safe(f'<a href="{obj.buktiBayar.url}" target="_blank">'
                           f'<img src="{obj.buktiBayar.url}" style="width: 40px; height: auto;" /></a>')
        return "-"
    thumb_bukti_bayar.short_description = "Bukti Bayar"
    
    def thumb_bukti_refund(self, obj):
        if obj.buktiRefund:
            return mark_safe(f'<a href="{obj.buktiRefund.url}" target="_blank">'
                           f'<img src="{obj.buktiRefund.url}" style="width: 50px; height: auto;" /></a>')
        return "-"
    thumb_bukti_refund.short_description = "Bukti Refund"
    
    def aksi(self, obj):
        change_url = reverse('admin:core_transaksi_change', args=[obj.idTransaksi])
        delete_url = reverse('admin:core_transaksi_delete', args=[obj.idTransaksi])
        
        buttons = [
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="View/Edit">'
            f'<i class="fa-solid fa-eye"></i></a>',
            f'<a href="{change_url}" class="btn btn-sm" style="margin-right: 5px;" title="Edit">'
            f'<i class="fa-solid fa-pen-to-square"></i></a>'
        ]
        
        # Add delete button if user has permission and request exists
        if hasattr(self, '_request') and self._request and self.has_delete_permission(self._request, obj):
            buttons.append(
                f'<a href="{delete_url}" class="btn btn-sm" style="color: #dc3545;" title="Delete">'
                f'<i class="fa-solid fa-trash"></i></a>'
            )
        
        return mark_safe(''.join(buttons))
    
    aksi.short_description = "Aksi"
    
    def get_queryset(self, request):
        self._request = request
        return super().get_queryset(request)
    
    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

admin.site.register(Pelanggan, PelangganAdmin)
admin.site.register(Produk, ProdukAdmin)
admin.site.register(Transaksi, TransaksiAdmin)
admin.site.register(Kurir, KurirAdmin)
