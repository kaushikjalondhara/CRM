/**
 * CRM Products Module
 * Manages product listing, search, filtering, and CRUD operations.
 */

let currentPage = 1;
let currentTotalPages = 1;
let selectedProductId = null;
let bulkSelection = null;

document.addEventListener('DOMContentLoaded', async () => {
  const user = await Auth.requireAuth();
  if (!user) return;

  UI.updateNotificationBadge();
  setupEventListeners();
  loadProducts();
});

function setupEventListeners() {
  // Bulk selection setup
  bulkSelection = UI.initBulkSelection({
    selectAllId: 'selectAll',
    rowSelector: '.product-row-cb',
    toolbarId: 'bulkActionsToolbar',
    countId: 'bulkSelectedCount'
  });

  // Import Products Button
  document.getElementById('importProductsBtn')?.addEventListener('click', () => {
    UI.openImportModal('products', () => {
      loadProducts();
    });
  });

  // Bulk Actions
  document.getElementById('bulkDeleteBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkDelete('products', ids, () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadProducts();
    });
  });

  document.getElementById('bulkStatusBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.bulkStatus('products', ids, [
      { value: 'active', label: 'Active' },
      { value: 'inactive', label: 'Inactive' },
      { value: 'out_of_stock', label: 'Out of Stock' }
    ], () => {
      if (bulkSelection) bulkSelection.clearSelection();
      loadProducts();
    });
  });

  document.getElementById('bulkExportBtn')?.addEventListener('click', () => {
    const ids = bulkSelection ? bulkSelection.getSelectedIds() : [];
    UI.exportData('products', 'csv', { ids: ids.join(',') });
  });

  document.getElementById('addProductBtn')?.addEventListener('click', () => {
    openAddProductModal();
  });

  document.getElementById('searchInput')?.addEventListener('input', debounce(() => {
    currentPage = 1;
    loadProducts();
  }, 350));

  document.getElementById('categoryFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadProducts();
  });

  document.getElementById('statusFilter')?.addEventListener('change', () => {
    currentPage = 1;
    loadProducts();
  });

  document.getElementById('clearFiltersBtn')?.addEventListener('click', () => {
    document.getElementById('searchInput').value = '';
    document.getElementById('categoryFilter').value = '';
    document.getElementById('statusFilter').value = '';
    currentPage = 1;
    loadProducts();
  });

  document.getElementById('prevPageBtn')?.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      loadProducts();
    }
  });

  document.getElementById('nextPageBtn')?.addEventListener('click', () => {
    if (currentPage < currentTotalPages) {
      currentPage++;
      loadProducts();
    }
  });

  document.getElementById('productForm')?.addEventListener('submit', handleProductSubmit);
  document.getElementById('confirmDeleteBtn')?.addEventListener('click', handleConfirmDelete);
}

async function loadProducts() {
  const tbody = document.getElementById('productsTableBody');
  if (!tbody) return;

  if (bulkSelection) bulkSelection.clearSelection();

  const search = document.getElementById('searchInput')?.value.trim() || '';
  const category = document.getElementById('categoryFilter')?.value || '';
  const status = document.getElementById('statusFilter')?.value || '';

  const params = new URLSearchParams({
    page: currentPage,
    per_page: 15
  });
  if (search) params.append('search', search);
  if (category) params.append('category', category);
  if (status) params.append('status', status);

  try {
    const res = await ApiClient.get(`/api/products?${params.toString()}`);
    if (!res.success) {
      tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #e53e3e; padding: 24px;">Failed to load products: ${UI.escapeHtml(res.data?.message || 'Server error')}</td></tr>`;
      return;
    }

    const { products, categories, total, page, total_pages } = res.data.data;
    currentPage = page;
    currentTotalPages = total_pages || 1;

    // Update Category Dropdown
    updateCategoryOptions(categories);

    // Update Summary Stats
    updateSummaryStats(products, total);

    // Update Pagination Controls
    document.getElementById('paginationInfo').textContent = `Showing ${products.length} of ${total} products (Page ${page} of ${currentTotalPages})`;
    document.getElementById('prevPageBtn').disabled = currentPage <= 1;
    document.getElementById('nextPageBtn').disabled = currentPage >= currentTotalPages;

    if (products.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; padding: 48px 16px;">
            <div style="font-size: 2.5rem; margin-bottom: 8px;">📦</div>
            <div style="font-weight: 600; font-size: 1.1rem; color: #2d3748;">No Products Found</div>
            <p style="color: #718096; margin-top: 4px;">Start by adding your first product or adjusting your search filters.</p>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = products.map(p => {
      let statusBadge = '';
      if (p.status === 'active') {
        statusBadge = '<span class="status-badge" style="background: #e6fffa; color: #234e52; border: 1px solid #b2f5ea;">Active</span>';
      } else if (p.status === 'out_of_stock') {
        statusBadge = '<span class="status-badge" style="background: #fff5f5; color: #9b2c2c; border: 1px solid #fed7d7;">Out of Stock</span>';
      } else {
        statusBadge = '<span class="status-badge" style="background: #edf2f7; color: #4a5568;">Inactive</span>';
      }

      return `
        <tr>
          <td style="text-align: center;"><input type="checkbox" class="product-row-cb" value="${p.id}"></td>
          <td style="font-family: monospace; font-size: 0.85rem; font-weight: 600; color: #4a5568;">${UI.escapeHtml(p.product_code)}</td>
          <td>
            <div style="font-weight: 600; color: #2d3748;">${UI.escapeHtml(p.name)}</div>
            ${p.description ? `<div style="font-size: 0.8rem; color: #718096; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${UI.escapeHtml(p.description)}</div>` : ''}
          </td>
          <td><span style="background: #f7fafc; border: 1px solid #e2e8f0; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">${UI.escapeHtml(p.category || 'Uncategorized')}</span></td>
          <td style="font-weight: 600; color: #1a202c;">${UI.formatCurrency(p.price)}</td>
          <td>${p.tax_percentage ? `${p.tax_percentage}%` : '0%'}</td>
          <td>${p.discount_percentage ? `${p.discount_percentage}%` : '0%'}</td>
          <td>
            <span style="font-weight: 600; ${p.stock <= 5 ? 'color: #e53e3e;' : 'color: #2b6cb0;'}">
              ${p.stock}
            </span>
          </td>
          <td>${statusBadge}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-secondary btn-sm" onclick="openEditProductModal(${p.id})">Edit</button>
            <button class="btn btn-danger btn-sm" style="margin-left: 4px;" onclick="openDeleteModal(${p.id}, '${UI.escapeHtml(p.name)}')">Delete</button>
          </td>
        </tr>
      `;
    }).join('');

  } catch (err) {
    console.error('Failed to load products', err);
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #e53e3e; padding: 24px;">An unexpected error occurred while fetching products.</td></tr>`;
  }
}

function updateCategoryOptions(categories) {
  const sel = document.getElementById('categoryFilter');
  if (!sel || !Array.isArray(categories)) return;

  const currentVal = sel.value;
  sel.innerHTML = '<option value="">All Categories</option>';
  categories.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c;
    opt.textContent = c;
    if (c === currentVal) opt.selected = true;
    sel.appendChild(opt);
  });
}

function updateSummaryStats(products, total) {
  document.getElementById('statTotalProducts').textContent = total || 0;
  const activeCount = products.filter(p => p.status === 'active').length;
  const outOfStockCount = products.filter(p => p.status === 'out_of_stock' || p.stock === 0).length;
  const totalStock = products.reduce((acc, p) => acc + (p.stock || 0), 0);

  document.getElementById('statActiveProducts').textContent = activeCount;
  document.getElementById('statOutOfStock').textContent = outOfStockCount;
  document.getElementById('statTotalStock').textContent = totalStock;
}

function openAddProductModal() {
  document.getElementById('productForm').reset();
  document.getElementById('productId').value = '';
  document.getElementById('productModalTitle').textContent = 'Add New Product / Service';
  document.getElementById('prodStatus').value = 'active';
  document.getElementById('prodStock').value = '10';
  document.getElementById('prodTax').value = '18.00';
  document.getElementById('prodDiscount').value = '0.00';
  UI.openModal('productModal');
}

async function openEditProductModal(productId) {
  try {
    const res = await ApiClient.get(`/api/products/${productId}`);
    if (!res.success) {
      UI.showToast(res.data?.message || 'Could not fetch product details', 'danger');
      return;
    }
    const p = res.data.product;
    document.getElementById('productId').value = p.id;
    document.getElementById('prodName').value = p.name || '';
    document.getElementById('prodCode').value = p.product_code || '';
    document.getElementById('prodCategory').value = p.category || '';
    document.getElementById('prodPrice').value = p.price || 0;
    document.getElementById('prodTax').value = p.tax_percentage || 0;
    document.getElementById('prodDiscount').value = p.discount_percentage || 0;
    document.getElementById('prodStock').value = p.stock || 0;
    document.getElementById('prodStatus').value = p.status || 'active';
    document.getElementById('prodDescription').value = p.description || '';

    document.getElementById('productModalTitle').textContent = `Edit Product: ${p.name}`;
    UI.openModal('productModal');
  } catch (err) {
    UI.showToast('Error opening edit modal', 'danger');
  }
}

async function handleProductSubmit(e) {
  e.preventDefault();
  const id = document.getElementById('productId').value;
  const isEdit = Boolean(id);

  const payload = {
    name: document.getElementById('prodName').value.trim(),
    product_code: document.getElementById('prodCode').value.trim() || undefined,
    category: document.getElementById('prodCategory').value.trim() || undefined,
    price: parseFloat(document.getElementById('prodPrice').value) || 0,
    tax_percentage: parseFloat(document.getElementById('prodTax').value) || 0,
    discount_percentage: parseFloat(document.getElementById('prodDiscount').value) || 0,
    stock: parseInt(document.getElementById('prodStock').value) || 0,
    status: document.getElementById('prodStatus').value,
    description: document.getElementById('prodDescription').value.trim() || undefined
  };

  const btn = document.getElementById('saveProductBtn');
  UI.setButtonLoading(btn, true, 'Saving...');

  try {
    let res;
    if (isEdit) {
      res = await ApiClient.put(`/api/products/${id}`, payload);
    } else {
      res = await ApiClient.post('/api/products', payload);
    }

    if (res.success) {
      UI.showToast(isEdit ? 'Product updated successfully' : 'Product created successfully', 'success');
      UI.closeModal('productModal');
      loadProducts();
    } else {
      UI.showToast(res.data?.message || 'Failed to save product', 'danger');
    }
  } catch (err) {
    UI.showToast('Error saving product', 'danger');
  } finally {
    UI.setButtonLoading(btn, false);
  }
}

function openDeleteModal(id, name) {
  selectedProductId = id;
  document.getElementById('deleteItemName').textContent = name;
  UI.openModal('deleteModal');
}

async function handleConfirmDelete() {
  if (!selectedProductId) return;
  const btn = document.getElementById('confirmDeleteBtn');
  UI.setButtonLoading(btn, true, 'Deleting...');

  try {
    const res = await ApiClient.delete(`/api/products/${selectedProductId}`);
    if (res.success) {
      UI.showToast(res.data?.message || 'Product removed successfully', 'success');
      UI.closeModal('deleteModal');
      loadProducts();
    } else {
      UI.showToast(res.data?.message || 'Failed to delete product', 'danger');
    }
  } catch (err) {
    UI.showToast('Error removing product', 'danger');
  } finally {
    UI.setButtonLoading(btn, false);
    selectedProductId = null;
  }
}

function debounce(fn, delay) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}
