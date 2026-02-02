let restaurantsCache = [];
let selectedType = 'dine-in';

function initAutocomplete() {
  const placeAutocomplete = document.getElementById('place-autocomplete');
  if (!placeAutocomplete) {
    setTimeout(initAutocomplete, 100);
    return;
  }

  placeAutocomplete.addEventListener('gmp-select', async (event) => {
    const place = event.placePrediction.toPlace();
    await place.fetchFields({
      fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'googleMapsLinks', 'googleMapsURI', 'types', 'priceLevel'],
    });
    console.log('Place', JSON.stringify(place.toJSON(), /* replacer */ null, /* space */ 2));

    if (place && place.id) {
      document.getElementById('place-id').value = place.id;

      // Extract name
      const name = place.displayName || 'UNKNOWN';
      const address = place.formattedAddress || 'UNKNOWN';
      const mapUri = place.googleMapsLinks?.placeURI || place.googleMapsURI || 'UNKNOWN';
      const directionsUri = place.googleMapsLinks?.directionsURI || 'UNKNOWN';
      const types = place.types || [];

      if (!types.includes('restaurant') && !types.includes('food')) {
        showMessage('Selected place is not a restaurant', true);
        document.getElementById('place-id').value = '';
        event.target.value = '';
        document.getElementById('submit-btn').disabled = true;
        document.getElementById('submit-btn').classList.add('opacity-50', 'cursor-not-allowed');
        return;
      }

      let city = "UNKNOWN";
      for (const component of place.addressComponents) {
        const types = component.types;
        if (types.includes('locality') || types.includes('postal_town')) {
          city = component.longText;
          break;
        }
      }

      // Store in global variable for form submission
      window.selectedPlaceData = {
        name: name,
        address: address,
        city: city,
        mapUri: mapUri,
        directionsUri: directionsUri,
        id: place.id,
        types: types,
      };

      document.getElementById('submit-btn').disabled = false;
      document.getElementById('submit-btn').classList.remove('opacity-50', 'cursor-not-allowed');
    }
  });
}

// Wait for both DOM and Google Maps API to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    // Give Google Maps API time to initialize
    setTimeout(initAutocomplete, 500);
  });
} else {
  setTimeout(initAutocomplete, 500);
}

async function loadRestaurants() {
  const res = await fetch('/api/restaurants');
  const data = await res.json();
  restaurantsCache = Array.isArray(data) ? data : [];
  renderList(restaurantsCache);
}

function renderList(items) {
  const container = document.getElementById('list');
  container.innerHTML = '';
  if (!Array.isArray(items) || items.length === 0) {
    container.innerHTML = '<div class="bg-white p-6 rounded-lg shadow text-center text-sm text-gray-500">No restaurants recorded yet.</div>';
    return;
  }
  items.forEach(r => container.appendChild(renderCard(r)));
}

async function loadCities() {
  const select = document.getElementById('filter-city');
  if (!select) return;
  try {
    const res = await fetch('/api/cities');
    if (res.ok) {
        const cities = await res.json();
        // Keep "All Cities" option
        select.innerHTML = '<option value="">All Cities</option>';
        cities.forEach(city => {
            const opt = document.createElement('option');
            opt.value = city;
            opt.textContent = city;
            select.appendChild(opt);
        });
    }
  } catch (err) {
      console.error('Failed to load cities', err);
  }
}

function applyFilters() {
  const q = (document.getElementById('search-input')?.value || '').trim().toLowerCase();
  const type = document.getElementById('filter-type')?.value || '';
  const city = document.getElementById('filter-city')?.value || '';
  const minRating = parseInt(document.getElementById('filter-rating')?.value || '0', 10);
  const filtered = restaurantsCache.filter(r => {
    if (q && !(r.name || '').toLowerCase().includes(q)) return false;
    if (type && r.type !== type) return false;
    if (city && r.city !== city) return false;
    if (minRating && (parseInt(r.rating, 10) || 0) < minRating) return false;
    return true;
  });
  renderList(filtered);
}

function renderCard(r) {
  const card = document.createElement('div');
  card.className = 'bg-white rounded-lg shadow-sm border border-gray-200 p-4 transition-shadow hover:shadow-md h-full flex flex-col justify-between';

  // 1. Header: Name (linked) and Badge
  const header = document.createElement('div');
  header.className = 'flex justify-between items-start mb-2';

  const titleLink = document.createElement('a');
  titleLink.href = r.mapUri || '#';
  titleLink.target = '_blank';
  titleLink.rel = 'noopener noreferrer';
  titleLink.className = 'text-lg font-bold text-gray-900 hover:text-indigo-600 line-clamp-1 mr-2';
  titleLink.textContent = r.name;
  header.appendChild(titleLink);

  const badge = document.createElement('span');
  badge.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800 capitalize flex-shrink-0';
  badge.textContent = (r.type || 'unknown').replace('-', ' ');
  header.appendChild(badge);

  card.appendChild(header);

  // 2. Body: City and Rating
  const body = document.createElement('div');
  
  // City
  if (r.city) {
    const cityEl = document.createElement('div');
    cityEl.className = 'flex items-center text-sm text-gray-500 mb-2 truncate';
    // Map pin icon
    cityEl.innerHTML = `<svg class="w-4 h-4 text-gray-400 mr-1 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg><span class="truncate">${escapeHtml(r.city)}</span>`;
    body.appendChild(cityEl);
  }

  // Rating
  const ratingEl = document.createElement('div');
  ratingEl.className = 'flex items-center mb-4';
  const ratingNum = Number(r.rating) || 0;
  ratingEl.innerHTML = renderStars(ratingNum) + `<span class="ml-2 text-sm font-medium text-gray-600">${ratingNum.toFixed(1)}</span>`;
  body.appendChild(ratingEl);
  
  card.appendChild(body);

  // 3. Actions Footer
  const footer = document.createElement('div');
  footer.className = 'mt-auto pt-3 border-t border-gray-100 flex items-center justify-between';

  // Left: Go actions
  const goBtn = document.createElement('a');
  goBtn.href = r.directionsUri || r.mapUri || '#'; // Prefer directionsUri
  goBtn.target = '_blank';
  goBtn.rel = 'noopener';
  goBtn.className = 'inline-flex items-center text-sm font-medium text-green-700 hover:text-green-800 bg-green-50 hover:bg-green-100 px-3 py-1.5 rounded-full transition-colors';
  goBtn.innerHTML = `
    <svg class="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 9l3 3m0 0l-3 3m3-3H8m13 0a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
    Let's go!
  `;
  footer.appendChild(goBtn);

  // Right: Edit/Delete
  const rightActions = document.createElement('div');
  rightActions.className = 'flex items-center space-x-1';

  const editBtn = document.createElement('button');
  editBtn.className = 'text-gray-400 hover:text-indigo-600 p-2 rounded-full hover:bg-indigo-50 transition-colors';
  editBtn.title = "Edit";
  editBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>`;
  editBtn.addEventListener('click', () => enterEditMode(r));
  rightActions.appendChild(editBtn);

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'text-gray-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-colors';
  deleteBtn.title = "Delete";
  deleteBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>`;
  deleteBtn.addEventListener('click', () => handleDelete(r));
  rightActions.appendChild(deleteBtn);

  footer.appendChild(rightActions);
  card.appendChild(footer);

  return card;
}

function renderStars(n) {
  const full = Math.max(0, Math.min(5, parseInt(n, 10) || 0));
  let out = '';
  for (let i = 0; i < 5; i++) {
    if (i < full) {
      out += '<svg class="w-5 h-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.262 3.89a1 1 0 00.95.69h4.1c.969 0 1.371 1.24.588 1.81l-3.32 2.41a1 1 0 00-.364 1.118l1.262 3.89c.3.921-.755 1.688-1.54 1.118l-3.32-2.41a1 1 0 00-1.176 0l-3.32 2.41c-.785.57-1.84-.197-1.54-1.118l1.262-3.89a1 1 0 00-.364-1.118L2.15 9.317c-.783-.57-.38-1.81.588-1.81h4.1a1 1 0 00.95-.69l1.262-3.89z"/></svg>';
    } else {
      out += '<svg class="w-5 h-5 text-gray-300" viewBox="0 0 20 20" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.262 3.89a1 1 0 00.95.69h4.1c.969 0 1.371 1.24.588 1.81l-3.32 2.41a1 1 0 00-.364 1.118l1.262 3.89c.3.921-.755 1.688-1.54 1.118l-3.32-2.41a1 1 0 00-1.176 0l-3.32 2.41c-.785.57-1.84-.197-1.54-1.118l1.262-3.89a1 1 0 00-.364-1.118L2.15 9.317c-.783-.57-.38-1.81.588-1.81h4.1a1 1 0 00.95-.69l1.262-3.89z"/></svg>';
    }
  }
  return out;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>\"]/g, s => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[s]));
}

// Make edit helpers global so card buttons can call them
function enterEditMode(r) {
  const modal = document.getElementById('restaurant-modal');
  if (modal) modal.classList.remove('hidden');
  const title = document.getElementById('modal-title');
  if (title) title.textContent = 'Edit Restaurant';
  const placeAutocomplete = document.getElementById('place-autocomplete');
  if (placeAutocomplete) {
    placeAutocomplete.value = r.name || '';
    // Make immutable in edit mode
    placeAutocomplete.classList.add('pointer-events-none', 'opacity-50');
  }
  document.getElementById('place-id').value = r.place_id || '';

  // update type buttons
  selectedType = r.type; // Sync global state
  const typeButtons = document.querySelectorAll('#type-buttons .type-button');
  typeButtons.forEach(btn => {
    if (btn.dataset.value === r.type) {
      btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.remove('hover:bg-gray-50');
    } else {
      btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.add('hover:bg-gray-50');
    }
  });

  const ratingStars = document.getElementById('rating-stars');
  if (ratingStars) {
    const ratingValue = Number(r.rating) || 0;
    ratingStars.dataset.rating = String(ratingValue);
    Array.from(ratingStars.children).forEach((star, i) => {
      if (i < ratingValue) {
        star.classList.add('text-yellow-400');
        star.classList.remove('text-gray-300');
      } else {
        star.classList.remove('text-yellow-400');
        star.classList.add('text-gray-300');
      }
    });
  }

  document.getElementById('edit-id').value = r.id;
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.textContent = 'Save changes';
    submitBtn.disabled = false;
    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function exitEditMode() {
  const form = document.getElementById('restaurant-form');
  if (form) form.reset();
  const placeAutocomplete = document.getElementById('place-autocomplete');
  if (placeAutocomplete) {
    placeAutocomplete.value = '';
    placeAutocomplete.classList.remove('pointer-events-none', 'opacity-50');
  }
  const modal = document.getElementById('restaurant-modal');
  if (modal) modal.classList.add('hidden');
  const title = document.getElementById('modal-title');
  if (title) title.textContent = 'Add Restaurant';
  document.getElementById('edit-id').value = '';
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.textContent = 'Add restaurant';
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
  }

  // reset type and rating
  selectedType = 'dine-in';
  const typeButtons = document.querySelectorAll('#type-buttons .type-button');
  typeButtons.forEach(btn => {
    if (btn.dataset.value === 'dine-in') {
      btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.remove('hover:bg-gray-50');
    } else {
      btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.add('hover:bg-gray-50');
    }
  });
  const ratingStars = document.getElementById('rating-stars');
  if (ratingStars) {
    ratingStars.dataset.rating = '5';
    Array.from(ratingStars.children).forEach((star, i) => {
      if (i < 5) {
        star.classList.add('text-yellow-400');
        star.classList.remove('text-gray-300');
      } else {
        star.classList.remove('text-yellow-400');
        star.classList.add('text-gray-300');
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('restaurant-modal');
  const addBtn = document.getElementById('add-restaurant-btn');
  const closeBtn = document.getElementById('close-modal-btn');
  const typeButtonsContainer = document.getElementById('type-buttons');
  const ratingStarsContainer = document.getElementById('rating-stars');

  // Type selection
  // selectedType is global
  if (typeButtonsContainer) {
    typeButtonsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.type-button');
      if (!btn) return;
      selectedType = btn.dataset.value;
      updateTypeButtons();
    });
  }

  function updateTypeButtons() {
    typeButtonsContainer.querySelectorAll('.type-button').forEach(btn => {
      if (btn.dataset.value === selectedType) {
        btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
        btn.classList.remove('hover:bg-gray-50');
      } else {
        btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
        btn.classList.add('hover:bg-gray-50');
      }
    });
  }

  // Rating selection
  if (ratingStarsContainer) {
    ratingStarsContainer.addEventListener('click', (e) => {
      const star = e.target.closest('svg');
      if (!star) return;
      const rating = Array.from(ratingStarsContainer.children).indexOf(star) + 1;
      ratingStarsContainer.dataset.rating = rating;
      updateRatingStars();
    });
  }

  function updateRatingStars() {
    const rating = parseInt(ratingStarsContainer.dataset.rating, 10);
    Array.from(ratingStarsContainer.children).forEach((star, i) => {
      if (i < rating) {
        star.classList.add('text-yellow-400');
        star.classList.remove('text-gray-300');
      } else {
        star.classList.remove('text-yellow-400');
        star.classList.add('text-gray-300');
      }
    });
  }

  const form = document.getElementById('restaurant-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Get data from the global variable set by autocomplete
      const placeData = window.selectedPlaceData || {};
      const name = placeData.name;
      const address = placeData.address;
      const city = placeData.city;
      const id = placeData.id;
      const type = selectedType;
      const rating = ratingStarsContainer.dataset.rating;
      const mapUri = placeData.mapUri;
      const directionsUri = placeData.directionsUri;
      const editId = document.getElementById('edit-id').value;
      const payload = { id, name, address, city, type, rating, mapUri, directionsUri };
      try {
        let res;
        if (editId) {
          res = await fetch(`/api/restaurants/${editId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } else {
          res = await fetch('/api/restaurants', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        }
        if (!res.ok) {
          const err = await res.json();
          showMessage(err.error || 'Failed to save', true);
        } else {
          exitEditMode();
          loadRestaurants();
          loadCities();
        }
      } catch (err) {
        showMessage('Network error', true);
      }
    });
  } else {
    console.warn('restaurant-form not found');
  }
  // wire up filters
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.addEventListener('input', applyFilters);

  // New filter UI handling
  const typeFilterGroup = document.getElementById('type-filter-group');
  if (typeFilterGroup) {
      typeFilterGroup.addEventListener('click', (e) => {
          const btn = e.target.closest('button');
          if (!btn) return;
          document.getElementById('filter-type').value = btn.dataset.value;
          
          // Update visual state
          typeFilterGroup.querySelectorAll('button').forEach(b => {
             if (b === btn) {
                 b.classList.remove('text-gray-500', 'hover:text-gray-900');
                 b.classList.add('bg-white', 'text-gray-900', 'shadow-sm');
             } else {
                 b.classList.add('text-gray-500', 'hover:text-gray-900');
                 b.classList.remove('bg-white', 'text-gray-900', 'shadow-sm');
             }
          });
          applyFilters();
      });
  }

  const ratingFilterGroup = document.getElementById('rating-filter-group');
  if (ratingFilterGroup) {
      ratingFilterGroup.addEventListener('click', (e) => {
          const btn = e.target.closest('button');
          if (!btn) return;
          document.getElementById('filter-rating').value = btn.dataset.value;
          
          // Update visual state
          ratingFilterGroup.querySelectorAll('button').forEach(b => {
             if (b === btn) {
                 b.classList.remove('border-gray-200', 'text-gray-600', 'bg-white', 'hover:border-indigo-300', 'hover:text-indigo-600');
                 b.classList.add('bg-indigo-50', 'border-indigo-200', 'text-indigo-700');
             } else {
                 b.classList.add('border-gray-200', 'text-gray-600', 'bg-white', 'hover:border-indigo-300', 'hover:text-indigo-600');
                 b.classList.remove('bg-indigo-50', 'border-indigo-200', 'text-indigo-700');
             }
          });
          applyFilters();
      });
  }

  // refresh removed; list can be reloaded programmatically via loadRestaurants()

  // Modal handling
  addBtn.addEventListener('click', () => {
    exitEditMode(); // Reset form for adding
    modal.classList.remove('hidden');
  });
  closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
  window.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.add('hidden');
    }
  });

  const cityFilter = document.getElementById('filter-city');
  if (cityFilter) {
      cityFilter.addEventListener('change', applyFilters);
  }

  loadCities();
  loadRestaurants();
});

function showMessage(msg, isError = false) {
  const el = document.getElementById('message');
  el.className = 'text-sm text-center pt-2 h-6 ' + (isError ? 'text-red-600' : 'text-green-600');
  el.textContent = msg;
  setTimeout(() => { el.textContent = '' }, 3000);
}

function handleDelete(r) {
  if (!r || !r.id) return;
  if (!confirm('Are you sure you want to delete this restaurant?')) return;
  fetch(`/api/restaurants/${r.id}`, {
    method: 'DELETE',
  })
    .then(res => {
      if (res.ok) {
        // Remove from cache and re-render
        restaurantsCache = restaurantsCache.filter(item => item.id !== r.id);
        renderList(restaurantsCache);
      } else {
        alert('Failed to delete restaurant.');
      }
    })
    .catch(() => alert('Failed to delete restaurant.'));
}