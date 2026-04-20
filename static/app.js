let restaurantsCache = [];
let activeWishlistFilter = false;
let selectedDiningOptions = 'both';
let allowedTypes = new Set();
let formWishlisted = false;
let restaurantToMarkVisited = null;
let markVisitedFromEditModal = false;

function csrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

const allowedTypesReady = fetch('/static/types.json')
  .then(r => r.json())
  .then(mapping => { allowedTypes = new Set(Object.keys(mapping)); })
  .catch(() => { });

const ICON_DINE_IN = `<svg class="w-3 h-3 shrink-0" fill="currentColor" aria-hidden="true"><use href="#icon-dine-in"/></svg>`;
const ICON_DELIVERY = `<svg class="w-3 h-3 shrink-0" fill="currentColor" aria-hidden="true"><use href="#icon-delivery"/></svg>`;
let currentDishes = [];
let newDishRating = 1; // 1 for up, 0 for down
let editingDishIndex = -1;

function getPriceLevel(place) {
  const priceLevelMap = {
    'INEXPENSIVE': 1,
    'MODERATE': 2,
    'EXPENSIVE': 3,
    'VERY_EXPENSIVE': 4
  };
  if (place.priceLevel && priceLevelMap[place.priceLevel]) {
    return priceLevelMap[place.priceLevel];
  }
  return null;
}

function getCity(place) {
  let city = "UNKNOWN";
  if (place.addressComponents) {
    for (const component of place.addressComponents) {
      const types = component.types;
      if (types.includes('locality') || types.includes('postal_town')) {
        city = component.longText;
        break;
      }
    }
  }
  return city;
}

function getOpeningHours(place) {
  return place.regularOpeningHours ? {
    periods: place.regularOpeningHours.periods,
    weekdayDescriptions: place.regularOpeningHours.weekdayDescriptions,
    utcOffsetMinutes: place.utcOffsetMinutes
  } : null;
}

function clearSelection() {
  document.getElementById('place-id').value = '';
  window.selectedPlaceData = null;
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
  }
}

/**
 * Validates a fetched Place and populates the add form.
 * @param {google.maps.places.Place} place - Already-fetched Place object.
 */
async function selectPlaceInForm(place) {
  try {
    const res = await fetch(`/api/restaurants/${place.id}`);
    if (res.ok) {
      showMessage('Restaurant already exists', true);
      clearSelection();
      return;
    }
  } catch (_) { }

  const types = place.types || [];
  if (!types.some(t => allowedTypes.has(t))) {
    showMessage('Selected place is not a restaurant', true);
    clearSelection();
    return;
  }

  window.selectedPlaceData = {
    name: place.displayName || 'UNKNOWN',
    address: place.formattedAddress || 'UNKNOWN',
    city: getCity(place),
    mapUri: place.googleMapsLinks?.placeURI || place.googleMapsURI || 'UNKNOWN',
    directionsUri: place.googleMapsLinks?.directionsURI || 'UNKNOWN',
    id: place.id,
    types,
    priceLevel: getPriceLevel(place),
    openingHours: getOpeningHours(place),
    latitude: place.location?.lat() ?? null,
    longitude: place.location?.lng() ?? null,
  };

  document.getElementById('place-id').value = place.id;

  const placeAutocomplete = document.getElementById('place-autocomplete');
  if (placeAutocomplete) placeAutocomplete.value = window.selectedPlaceData.name;

  displayAddress(window.selectedPlaceData.address);
  displayOpeningHours(window.selectedPlaceData.openingHours);

  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }
  return;
}

function initAutocomplete() {
  const placeAutocomplete = document.getElementById('place-autocomplete');
  if (!placeAutocomplete) {
    setTimeout(initAutocomplete, 100);
    return;
  }

  // Listen for input events to clear selection when user types or clears the input.
  placeAutocomplete.addEventListener('input', () => {
    clearSelection();
    displayAddress(null);
    displayOpeningHours(null);
    clearMessage();
  });

  // Listen for events where the user clicks the "x" button to clear the selection.
  placeAutocomplete.addEventListener('click', () => {
    setTimeout(() => {
      // If value is empty, it means X was clicked
      if (!placeAutocomplete.value) {
        clearSelection();
        displayAddress(null);
        displayOpeningHours(null);
        clearMessage();
      }
    }, 0);
  });

  placeAutocomplete.addEventListener('gmp-select', async (event) => {
    await allowedTypesReady;
    const place = event.placePrediction.toPlace();
    await place.fetchFields({
      fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'googleMapsLinks', 'googleMapsURI', 'types', 'priceLevel', 'regularOpeningHours', 'utcOffsetMinutes'],
    });
    if (window.DEBUG) console.log(JSON.stringify(place.toJSON(), /* replacer */ null, /* space */ 2));

    if (place?.id) {
      await selectPlaceInForm(place);
    }
  });
}

function displayAddress(address) {
  const container = document.getElementById('address-container');
  const display = document.getElementById('address-display');
  if (!container || !display) return;

  if (!address || address === 'UNKNOWN') {
    container.classList.add('hidden');
    display.innerHTML = '';
    return;
  }

  display.innerHTML = `<span class="inline-flex items-center gap-1"><svg class="w-3.5 h-3.5 shrink-0 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/></svg><span>${address}</span></span>`;
  container.classList.remove('hidden');
}

function displayOpeningHours(openingHours) {
  const container = document.getElementById('opening-hours-container');
  const list = document.getElementById('opening-hours-list');
  if (!container || !list) return;

  if (!openingHours || !openingHours.weekdayDescriptions || openingHours.weekdayDescriptions.length === 0) {
    container.classList.add('hidden');
    list.innerHTML = '';
    return;
  }

  list.innerHTML = '';
  list.className = 'text-xs text-gray-500';

  let today;
  if (openingHours.utcOffsetMinutes !== undefined && openingHours.utcOffsetMinutes !== null) {
    const now = new Date();
    const utcMs = now.getTime();
    const restaurantMs = utcMs + (openingHours.utcOffsetMinutes * 60000);
    const restaurantDate = new Date(restaurantMs);
    const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    today = days[restaurantDate.getUTCDay()];
  } else {
    today = new Date().toLocaleDateString('en-US', { weekday: 'long' });
  }

  const todayDescRaw = openingHours.weekdayDescriptions.find(d => d.startsWith(today));

  // Create Details element
  const details = document.createElement('details');
  details.className = 'group relative';

  // Summary (Today's hours)
  const summary = document.createElement('summary');
  summary.className = 'flex items-center cursor-pointer text-gray-500 select-none list-none group-open:absolute group-open:right-0 group-open:top-0';
  // Hide default marker for some browsers if flex doesn't cover it (e.g. Safari)
  summary.style.listStyle = 'none';

  let summaryTextWrapper = document.createElement('div');
  summaryTextWrapper.className = 'flex-1 grid grid-cols-[auto_1fr] gap-x-4 group-open:hidden';

  if (todayDescRaw) {
    const firstColonIndex = todayDescRaw.indexOf(':');
    if (firstColonIndex !== -1) {
      const dayName = todayDescRaw.substring(0, firstColonIndex);
      const hours = todayDescRaw.substring(firstColonIndex + 1).trim();
      summaryTextWrapper.innerHTML = `<div>${dayName}</div><div>${hours}</div>`;
    } else {
      summaryTextWrapper.textContent = todayDescRaw;
      summaryTextWrapper.className = 'flex-1 group-open:hidden';
    }
  } else {
    summaryTextWrapper.textContent = "See opening hours";
    summaryTextWrapper.className = 'flex-1 italic text-gray-400 group-open:hidden';
  }

  const icon = document.createElement('div');
  icon.className = 'ml-auto';
  icon.innerHTML = `<svg class="w-4 h-4 text-gray-400 transform group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>`;

  summary.appendChild(summaryTextWrapper);
  summary.appendChild(icon);
  details.appendChild(summary);

  // Full list
  const grid = document.createElement('div');
  grid.className = 'grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-gray-500 font-normal pr-6';

  openingHours.weekdayDescriptions.forEach(dayDesc => {
    const firstColonIndex = dayDesc.indexOf(':');

    if (firstColonIndex !== -1) {
      const dayName = dayDesc.substring(0, firstColonIndex);
      const hours = dayDesc.substring(firstColonIndex + 1).trim();

      const dayEl = document.createElement('div');
      dayEl.textContent = dayName;

      const hoursEl = document.createElement('div');
      hoursEl.textContent = hours;

      if (dayName === today) {
        dayEl.className = 'text-gray-900 whitespace-nowrap';
        hoursEl.className = 'text-gray-900';
      } else {
        dayEl.className = 'text-gray-700 whitespace-nowrap';
      }

      grid.appendChild(dayEl);
      grid.appendChild(hoursEl);
    } else {
      // Fallback
      const fullEl = document.createElement('div');
      fullEl.className = 'col-span-2';
      if (dayDesc.startsWith(today)) {
        fullEl.classList.add('text-gray-900');
      }
      fullEl.textContent = dayDesc;
      grid.appendChild(fullEl);
    }
  });

  details.appendChild(grid);
  list.appendChild(details);

  container.classList.remove('hidden');
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
  populateCityFilter();
  populateCuisineFilter();
  filterAndRender();
}

// ---------------------------------------------------------------------------
// Map view
// ---------------------------------------------------------------------------

let mapInstance = null;
let mapMarkers = [];
let userLocationMarker = null;
let lastKnownPosition = null;
let activeView = 'list'; // 'list' | 'map'

function setView(view) {
  activeView = view;
  const listEl = document.getElementById('list');
  const mapEl = document.getElementById('map-view');
  const listBtn = document.getElementById('view-list-btn');
  const mapBtn = document.getElementById('view-map-btn');

  const activeClasses = ['bg-indigo-50', 'text-indigo-700'];
  const inactiveClasses = ['bg-white', 'text-gray-500', 'hover:text-gray-700'];

  if (view === 'map') {
    listEl.classList.add('hidden');
    mapEl.classList.remove('hidden');
    listBtn.classList.remove(...activeClasses);
    listBtn.classList.add(...inactiveClasses);
    mapBtn.classList.remove(...inactiveClasses);
    mapBtn.classList.add(...activeClasses);
  } else {
    mapEl.classList.add('hidden');
    listEl.classList.remove('hidden');
    mapBtn.classList.remove(...activeClasses);
    mapBtn.classList.add(...inactiveClasses);
    listBtn.classList.remove(...inactiveClasses);
    listBtn.classList.add(...activeClasses);
  }
  filterAndRender();
}

function updateUserLocation(pos) {
  const userLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
  if (userLocationMarker) {
    userLocationMarker.position = userLocation;
  } else {
    const dot = document.createElement('div');
    dot.style.cssText = 'width:14px;height:14px;background:#4285f4;border:2px solid #fff;border-radius:50%;box-shadow:0 1px 4px rgba(0,0,0,.4)';
    userLocationMarker = new google.maps.marker.AdvancedMarkerElement({
      position: userLocation,
      map: mapInstance,
      title: 'Your location',
      content: dot,
    });
  }
}

function locateMe(pos) {
  updateUserLocation(pos);

  mapInstance.setCenter({ lat: pos.coords.latitude, lng: pos.coords.longitude });
  mapInstance.setZoom(12);
}

function renderMap(restaurants) {
  if (!window.google?.maps?.Map) return;

  const container = document.getElementById('map-container');
  if (!container) return;

  const cardPanel = document.getElementById('map-card-panel');
  if (!mapInstance) {
    mapInstance = new google.maps.Map(container, {
      zoom: 2,
      center: { lat: 20, lng: 0 },
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      cameraControl: false,
      gestureHandling: 'greedy',
      mapId: container.dataset.mapId,
    });

    const fullscreenBtn = document.getElementById('map-fullscreen-btn');
    if (fullscreenBtn) {
      const iconExpand = document.getElementById('map-fullscreen-icon-expand');
      const iconShrink = document.getElementById('map-fullscreen-icon-shrink');
      fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
          container.requestFullscreen();
        } else {
          document.exitFullscreen();
        }
      });
      document.addEventListener('fullscreenchange', () => {
        const isFs = !!document.fullscreenElement;
        iconExpand.classList.toggle('hidden', isFs);
        iconShrink.classList.toggle('hidden', !isFs);
      });
      mapInstance.controls[google.maps.ControlPosition.RIGHT_TOP].push(fullscreenBtn);
    }
    mapInstance.addListener('click', () => {
      cardPanel.innerHTML = '';
      cardPanel.classList.add('hidden');
    });
    if (navigator.geolocation) {
      const geoOptions = { enableHighAccuracy: false, maximumAge: 30000, timeout: 10000 };
      navigator.geolocation.watchPosition(
        pos => {
          lastKnownPosition = pos;
          updateUserLocation(pos);
        },
        () => { },
        geoOptions
      );

      const locateBtn = document.getElementById('locate-me-btn');
      if (locateBtn) {
        locateBtn.addEventListener('click', () => {
          if (lastKnownPosition) {
            locateMe(lastKnownPosition);
          } else {
            navigator.geolocation.getCurrentPosition(
              pos => { lastKnownPosition = pos; locateMe(pos); },
              () => { },
              geoOptions
            );
          }
        });
        mapInstance.controls[google.maps.ControlPosition.RIGHT_TOP].push(locateBtn);
      }
    }
  }

  // Clear existing markers
  mapMarkers.forEach(m => (m.map = null));
  mapMarkers = [];

  const visible = restaurants.filter(r => r.latitude != null && r.longitude != null);

  if (visible.length === 0) return;

  const bounds = new google.maps.LatLngBounds();

  visible.forEach(r => {
    const position = { lat: r.latitude, lng: r.longitude };
    const pill = document.createElement('div');
    pill.style.cssText = 'background:#4f46e5;color:#fff;padding:4px 10px;border-radius:9999px;font-size:12px;font-weight:600;white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.3);cursor:pointer';
    pill.textContent = r.name;

    const marker = new google.maps.marker.AdvancedMarkerElement({
      position,
      map: mapInstance,
      title: r.name,
      content: pill,
      collisionBehavior: google.maps.CollisionBehavior.OPTIONAL_AND_HIDES_LOWER_PRIORITY,
    });

    marker.addListener('click', () => {
      cardPanel.innerHTML = '';
      cardPanel.appendChild(renderCard(r));
      cardPanel.classList.remove('hidden');
    });

    mapMarkers.push(marker);
    bounds.extend(position);
  });

  if (visible.length === 1) {
    mapInstance.setCenter(bounds.getCenter());
    mapInstance.setZoom(14);
  } else {
    mapInstance.fitBounds(bounds);
  }
}

function getNotesLineCount(notes) {
  if (!notes) return 0;
  return Math.min(notes.split('\n').length, 3);
}

function estimateCardHeight(restaurant) {
  let h = 160; // base: header + city/badge + rating/price + footer
  if (restaurant.cuisines.length > 0) h += 28;
  const noteLines = getNotesLineCount(restaurant.notes);
  if (noteLines > 0) h += 16 + noteLines * 20 + 16; // padding (p-2=16) + lines*lineHeight + mb-4
  if (restaurant.dishes && restaurant.dishes.length > 0) {
    h += 28; // "DISHES" title + top border
    const shown = Math.min(restaurant.dishes.length, 10);
    h += shown * 36; // each dish item
    if (restaurant.dishes.length > 10) h += 24; // "+ N more"
  }
  return h;
}

function renderRestaurants(restaurants) {
  const container = document.getElementById('list');
  const fab = document.getElementById('add-restaurant-btn-fab');
  container.innerHTML = '';
  if (!Array.isArray(restaurants) || restaurants.length === 0) {
    const viewCount = restaurantsCache.filter(r => r.wishlisted === activeWishlistFilter).length;
    if (viewCount === 0) {
      fab.classList.add('hidden');
      const subtitle = activeWishlistFilter
        ? 'Is there a restaurant you would like to visit?'
        : 'Get started by adding your first favorite dining spot.';
      container.innerHTML = `
            <div class="col-span-full bg-white p-12 rounded-lg shadow-sm border border-gray-100 text-center" style="column-span: all;">
                 <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                <h3 class="mt-2 text-sm font-medium text-gray-900">Nothing here yet</h3>
                <p class="mt-1 text-sm text-gray-500">${subtitle}</p>
                <div class="mt-6">
                    <button id="empty-state-add-btn" class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                        Add Restaurant
                    </button>
                </div>
            </div>`;
      const emptyStateAddBtn = document.getElementById('empty-state-add-btn');
      if (emptyStateAddBtn) {
        emptyStateAddBtn.addEventListener('click', () => {
          document.getElementById('add-restaurant-btn').click();
        });
      }
    } else {
      // Filters hid everything
      container.innerHTML = `
            <div class="col-span-full bg-white p-12 rounded-lg shadow-sm border border-gray-100 text-center" style="column-span: all;">
                <svg class="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <h3 class="mt-2 text-sm font-medium text-gray-900">No matches found</h3>
                <p class="mt-1 text-sm text-gray-500">Try adjusting your search or filters to find what you're looking for.</p>
                <div class="mt-6">
                    <button id="clear-filters-btn" type="button" class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                        Clear Filters
                    </button>
                </div>
            </div>`;
      const clearBtn = document.getElementById('clear-filters-btn');
      if (clearBtn) {
        clearBtn.addEventListener('click', clearFilters);
      }
    }
    return;
  }
  // Masonry: place each card into the shortest column for balanced heights
  const colCount = window.innerWidth >= 1024 ? 3 : window.innerWidth >= 640 ? 2 : 1;
  const columns = Array.from({ length: colCount }, () => {
    const col = document.createElement('div');
    col.className = 'flex flex-col gap-6';
    return col;
  });

  const colHeights = new Array(colCount).fill(0);
  const gap = 24; // gap-6 = 1.5rem = 24px
  const cards = restaurants.map(r => renderCard(r));

  cards.forEach((card, i) => {
    const h = estimateCardHeight(restaurants[i]);

    // Find the shortest column
    let minIdx = 0;
    for (let j = 1; j < colCount; j++) {
      if (colHeights[j] < colHeights[minIdx]) minIdx = j;
    }
    columns[minIdx].appendChild(card);
    colHeights[minIdx] += h + gap;
  });

  columns.forEach(col => container.appendChild(col));
  fab.classList.remove('hidden');
}

function populateCityFilter() {
  const container = document.getElementById('city-filter-options');
  if (!container) return;

  const cities = [...new Set(restaurantsCache.filter(r => r.wishlisted === activeWishlistFilter).map(r => r.city).filter(Boolean))].sort();

  const firstBtn = container.firstElementChild;
  container.innerHTML = '';
  if (firstBtn) container.appendChild(firstBtn);

  cities.forEach(city => {
    const btn = document.createElement('button');
    btn.className = 'block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100';
    btn.dataset.value = city;
    btn.dataset.label = city;
    btn.textContent = city;
    container.appendChild(btn);
  });
}

function populateCuisineFilter() {
  const container = document.getElementById('cuisine-filter-options');
  if (!container) return;

  const cuisines = [...new Set(restaurantsCache.filter(r => r.wishlisted === activeWishlistFilter).flatMap(r => r.cuisines || []).filter(Boolean))].sort();

  const firstBtn = container.firstElementChild;
  container.innerHTML = '';
  if (firstBtn) container.appendChild(firstBtn);

  cuisines.forEach(cuisine => {
    const btn = document.createElement('button');
    btn.className = 'block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100';
    btn.dataset.value = cuisine;
    btn.dataset.label = cuisine;
    btn.textContent = cuisine;
    container.appendChild(btn);
  });
}

function setTriggerActive(trigger, isActive) {
  if (isActive) {
    trigger.classList.remove('bg-white', 'border-gray-300', 'text-gray-700');
    trigger.classList.add('bg-indigo-50', 'border-indigo-200', 'text-indigo-700');
  } else {
    trigger.classList.remove('bg-indigo-50', 'border-indigo-200', 'text-indigo-700');
    trigger.classList.add('bg-white', 'border-gray-300', 'text-gray-700');
  }
}

function clearFilters() {
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.value = '';

  document.getElementById('filter-dining-options').value = '';
  document.getElementById('filter-city').value = '';
  document.getElementById('filter-cuisine').value = '';
  document.getElementById('filter-rating').value = '';
  document.getElementById('filter-price').value = '';
  document.getElementById('filter-status').value = '';

  // Reset Dropdown UI
  document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
    const trigger = dropdown.querySelector('.dropdown-trigger');
    const defaultText = trigger.dataset.default;

    // Reset text
    const labelSpan = trigger.querySelector('.filter-label');
    if (labelSpan) labelSpan.innerHTML = defaultText;
    setTriggerActive(trigger, false);
  });

  filterAndRender();
}



function sortRestaurants(restaurants) {
  const currentSort = document.getElementById('current-sort')?.value || '';
  const byDate = (a, b) => (b.createdAt || '').localeCompare(a.createdAt || '');
  if (currentSort === 'name') {
    restaurants.sort((a, b) => (a.name || '').localeCompare(b.name || '') || byDate(a, b));
  } else if (currentSort === 'rating') {
    restaurants.sort((a, b) => ((b.rating || 0) - (a.rating || 0)) || byDate(a, b));
  } else if (currentSort === 'price') {
    const price = r => r.priceLevel || Infinity;
    restaurants.sort((a, b) => (price(a) - price(b)) || byDate(a, b));
  } else {
    restaurants.sort(byDate);
  }
  return restaurants;
}

function filterAndRender() {
  const searchInput = (document.getElementById('search-input')?.value || '').trim().toLowerCase();
  const diningOptions = document.getElementById('filter-dining-options')?.value || '';
  const city = document.getElementById('filter-city')?.value || '';
  const cuisine = document.getElementById('filter-cuisine')?.value || '';
  const minRating = !activeWishlistFilter ? parseInt(document.getElementById('filter-rating')?.value || '0', 10) : 0;
  const price = document.getElementById('filter-price')?.value || '';
  const status = document.getElementById('filter-status')?.value || '';

  const hasActiveFilters = searchInput || diningOptions || city || cuisine || minRating > 0 || price || status;
  const topClearBtn = document.getElementById('top-clear-filters-btn');
  if (topClearBtn) topClearBtn.classList.toggle('!hidden', !hasActiveFilters);

  const filtered = restaurantsCache.filter(r => {
    if (r.wishlisted !== activeWishlistFilter) return false;
    if (searchInput && !(r.name || '').toLowerCase().includes(searchInput)) return false;
    if (diningOptions && r.diningOptions !== diningOptions && r.diningOptions !== 'both') return false;
    if (city && r.city !== city) return false;
    if (cuisine && !(r.cuisines || []).includes(cuisine)) return false;
    if (minRating && (parseInt(r.rating, 10) || 0) < minRating) return false;
    if (price && (r.priceLevel && r.priceLevel > parseInt(price, 10))) return false;
    if (status) {
      const os = getOpeningStatus(r.openingHours);
      const isOpen = os ? os.isOpen : false;
      if (status === 'open' && !isOpen) return false;
      if (status === 'closed' && isOpen) return false;
    }

    return true;
  });
  if (activeView === 'map') renderMap(sortRestaurants(filtered));
  else renderRestaurants(sortRestaurants(filtered));
}

function getOpeningStatus(openingHours) {
  if (!openingHours || !openingHours.periods) return null;

  let now = new Date();

  // Adjust to place's timezone if available
  if (openingHours.utcOffsetMinutes !== undefined && openingHours.utcOffsetMinutes !== null) {
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    now = new Date(utc + (openingHours.utcOffsetMinutes * 60000));
  }

  const day = now.getDay(); // 0-6 Sun-Sat
  const hour = now.getHours();
  const min = now.getMinutes();

  // Current time in minutes from start of week (Sunday 00:00)
  const currentMin = day * 1440 + hour * 60 + min;

  let isOpen = false;

  for (const period of openingHours.periods) {
    if (!period.open) continue;

    // If always open (Check for 24/7 locations where close time is missing)
    if (!period.close) return { isOpen: true };

    const openMin = period.open.day * 1440 + period.open.hour * 60 + period.open.minute;
    let closeMin = period.close.day * 1440 + period.close.hour * 60 + period.close.minute;

    if (closeMin < openMin) {
      // Wraps around week end
      if (currentMin >= openMin || currentMin < closeMin) {
        isOpen = true;
        break;
      }
    } else {
      // Normal period
      if (currentMin >= openMin && currentMin < closeMin) {
        isOpen = true;
        break;
      }
    }
  }

  return { isOpen };
}

function renderCard(r) {
  const card = document.createElement('div');
  card.className = 'bg-white rounded-lg shadow-sm border border-gray-200 p-4 transition-shadow hover:shadow-md flex flex-col justify-between cursor-pointer';
  card.addEventListener('click', () => enterEditMode(r));

  // 1. Header: Name (linked) and Badge
  const header = document.createElement('div');
  header.className = 'flex justify-between items-center mb-2';

  const titleLink = document.createElement('span');
  titleLink.className = 'text-lg font-bold text-gray-900 line-clamp-1 mr-2';
  titleLink.textContent = r.name;
  header.appendChild(titleLink);

  const metaDiv = document.createElement('div');
  metaDiv.className = 'flex items-center space-x-2 shrink-0';

  const makeBadge = (html, title) => {
    const b = document.createElement('span');
    b.className = 'inline-flex items-center p-1 rounded bg-green-100 text-green-800';
    b.innerHTML = html;
    if (title) b.title = title;
    return b;
  };

  let badges = [];
  if (r.diningOptions === 'dine-in') {
    badges = [makeBadge(ICON_DINE_IN, 'Dine-in')];
  } else if (r.diningOptions === 'delivery') {
    badges = [makeBadge(ICON_DELIVERY, 'Delivery')];
  } else if (r.diningOptions === 'both') {
    badges = [makeBadge(ICON_DINE_IN, 'Dine-in'), makeBadge(ICON_DELIVERY, 'Delivery')];
  } else {
    const b = document.createElement('span');
    b.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize bg-indigo-100 text-indigo-800';
    b.textContent = (r.diningOptions || 'unknown').replace('-', ' ');
    badges = [b];
  }

  const status = getOpeningStatus(r.openingHours);
  if (status) {
    const statusContainer = document.createElement('span');
    statusContainer.className = `inline-flex items-center text-xs font-medium ml-2 ${status.isOpen ? 'text-green-700' : 'text-red-700'}`;

    const dot = document.createElement('span');
    dot.className = `w-2 h-2 mr-1 rounded-full ${status.isOpen ? 'bg-green-500' : 'bg-red-500'}`;

    const text = document.createTextNode(status.isOpen ? 'Open' : 'Closed');

    statusContainer.appendChild(dot);
    statusContainer.appendChild(text);
    metaDiv.appendChild(statusContainer);
  }

  header.appendChild(metaDiv);

  card.appendChild(header);

  // 2. Body: City, Price, and Rating
  const body = document.createElement('div');

  // Second line: City (left) + Price (right)
  const secondLine = document.createElement('div');
  secondLine.className = 'flex items-center justify-between mb-2 text-sm';

  // City
  const cityEl = document.createElement('div');
  cityEl.className = 'flex items-center text-gray-500 truncate mr-2';
  if (r.city) {
    cityEl.innerHTML = `<svg class="w-4 h-4 text-gray-400 mr-1 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"></path></svg><span class="truncate">${escapeHtml(r.city)}</span>`;
  }
  secondLine.appendChild(cityEl);

  // Type moved here
  const badgeWrapper = document.createElement('div');
  badgeWrapper.className = 'flex items-center gap-1';
  badges.forEach(b => badgeWrapper.appendChild(b));
  secondLine.appendChild(badgeWrapper);

  body.appendChild(secondLine);

  // Third line: Rating (left) + Price (right)
  const thirdLine = document.createElement('div');
  thirdLine.className = 'flex items-center justify-between mb-4';

  if (!r.wishlisted) {
    // Rating
    const ratingEl = document.createElement('div');
    ratingEl.className = 'flex items-center';
    const ratingNum = Number(r.rating) || 0;
    ratingEl.innerHTML = renderStars(ratingNum) + `<span class="ml-2 text-sm font-medium text-gray-600">${ratingNum.toFixed(1)}</span>`;
    thirdLine.appendChild(ratingEl);
  } else {
    // Greyed-out rating — clicking opens mark-as-visited modal
    const ratingEl = document.createElement('div');
    ratingEl.className = 'flex items-center cursor-pointer group';
    ratingEl.title = 'Mark as visited';
    ratingEl.innerHTML = renderStars(0);
    ratingEl.addEventListener('click', (e) => {
      e.stopPropagation();
      openMarkVisitedModal(r, false);
    });
    thirdLine.appendChild(ratingEl);
  }

  // Price
  if (r.priceLevel) {
    const priceSpan = document.createElement('div');
    priceSpan.className = 'font-semibold text-gray-500 font-mono tracking-widest shrink-0';
    priceSpan.textContent = '$'.repeat(r.priceLevel);
    thirdLine.appendChild(priceSpan);
  }

  body.appendChild(thirdLine);

  // Cuisine type badges
  const cuisines = r.cuisines;
  if (cuisines.length > 0) {
    const typesRow = document.createElement('div');
    typesRow.className = 'flex flex-wrap gap-1 mb-4';
    cuisines.forEach(label => {
      const badge = document.createElement('span');
      badge.className = 'inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-indigo-50 text-indigo-700 border border-indigo-100';
      badge.textContent = label;
      typesRow.appendChild(badge);
    });
    body.appendChild(typesRow);
  }
  if (r.notes) {
    const notesEl = document.createElement('div');
    notesEl.className = 'mb-4 text-sm text-gray-600 bg-gray-50 p-2 rounded border border-gray-100 italic';
    const lines = r.notes.split('\n').slice(0, 3);
    lines.forEach(line => {
      const lineEl = document.createElement('div');
      lineEl.className = 'truncate';
      lineEl.textContent = line;
      notesEl.appendChild(lineEl);
    });
    body.appendChild(notesEl);
  }

  // Dishes
  if (r.dishes && r.dishes.length > 0) {
    const dishesEl = document.createElement('div');
    dishesEl.className = 'mb-4 pt-3 border-t border-gray-100 space-y-2';

    const dishesTitle = document.createElement('h4');
    dishesTitle.className = 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2';
    dishesTitle.textContent = 'Dishes';
    dishesEl.appendChild(dishesTitle);

    r.dishes.slice(0, 10).forEach(d => {
      const dishItem = document.createElement('div');
      dishItem.className = 'bg-gray-50 rounded border border-gray-100 flex items-start justify-between p-2';

      const contentDiv = document.createElement('div');
      contentDiv.className = 'flex-1 min-w-0 mr-2';

      const headerDiv = document.createElement('div');
      headerDiv.className = 'flex items-center gap-2';

      const ratingIcon = document.createElement('span');
      ratingIcon.className = 'shrink-0 mt-0.5';
      if (d.rating === 1) { // Up
        ratingIcon.innerHTML = `
                <div class="p-1 rounded-md bg-green-100 text-green-700">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                    </svg>
                </div>`;
      } else { // Down
        ratingIcon.innerHTML = `
                <div class="p-1 rounded-md bg-red-100 text-red-700">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
                    </svg>
                </div>`;
      }

      const nameSpan = document.createElement('span');
      nameSpan.className = 'text-sm font-medium text-gray-900 truncate';
      nameSpan.textContent = d.name;
      headerDiv.appendChild(ratingIcon);
      headerDiv.appendChild(nameSpan);
      contentDiv.appendChild(headerDiv);
      dishItem.appendChild(contentDiv);
      dishesEl.appendChild(dishItem);
    });

    if (r.dishes.length > 10) {
      const remaining = r.dishes.length - 10;
      const moreDishes = document.createElement('div');
      moreDishes.className = 'mt-2 text-center text-xs font-medium text-gray-400 italic';
      moreDishes.textContent = `+ ${remaining} more`;
      dishesEl.appendChild(moreDishes);
    }
    body.appendChild(dishesEl);
  }

  card.appendChild(body);

  // 3. Actions Footer
  const footer = document.createElement('div');
  footer.className = 'mt-auto pt-3 border-t border-gray-100 flex items-center justify-between';

  // Left: Go actions
  const leftActions = document.createElement('div');
  leftActions.className = 'flex items-center';

  const mapsBtn = document.createElement('a');
  mapsBtn.href = r.mapUri || '#';
  mapsBtn.target = '_blank';
  mapsBtn.rel = 'noopener';
  mapsBtn.title = 'Open in Google Maps';
  mapsBtn.className = 'text-gray-400 hover:text-red-500 p-2 rounded-full hover:bg-red-50 transition-colors';
  mapsBtn.innerHTML = `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>`;
  mapsBtn.addEventListener('click', (e) => e.stopPropagation());
  leftActions.appendChild(mapsBtn);

  const goBtn = document.createElement('a');
  goBtn.href = r.directionsUri || r.mapUri || '#'; // Prefer directionsUri
  goBtn.target = '_blank';
  goBtn.rel = 'noopener';
  goBtn.title = 'Navigate';
  goBtn.className = 'text-gray-400 hover:text-blue-600 p-2 rounded-full hover:bg-blue-50 transition-colors';
  goBtn.innerHTML = `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg>`;
  goBtn.addEventListener('click', (e) => e.stopPropagation());
  leftActions.appendChild(goBtn);

  if (r.mapUri && r.mapUri !== 'UNKNOWN') {
    const shareBtn = document.createElement('button');
    shareBtn.title = 'Share';
    shareBtn.className = 'text-gray-400 hover:text-green-600 p-2 rounded-full hover:bg-green-50 transition-colors relative';
    shareBtn.innerHTML = `<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>`;
    shareBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const url = r.mapUri;
      const checkmark = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`;
      const showCopied = () => {
        const original = shareBtn.innerHTML;
        shareBtn.innerHTML = checkmark;
        shareBtn.classList.add('text-green-600');
        setTimeout(() => { shareBtn.innerHTML = original; shareBtn.classList.remove('text-green-600'); }, 2000);
      };
      const copyFallback = () => {
        // Works on HTTP / non-secure contexts
        const ta = document.createElement('textarea');
        ta.value = url;
        ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand('copy'); showCopied(); } catch (_) { }
        document.body.removeChild(ta);
      };
      if (navigator.share) {
        try {
          await navigator.share({ title: r.name, url });
          return;
        } catch (err) {
          if (err.name === 'AbortError') return;
          // share failed (e.g. unsupported data) — fall through to copy
        }
      }
      try {
        await navigator.clipboard.writeText(url);
        showCopied();
      } catch (_) {
        copyFallback();
      }
    });
    leftActions.appendChild(shareBtn);
  }

  footer.appendChild(leftActions);

  // Right: Edit/Delete
  const rightActions = document.createElement('div');
  rightActions.className = 'flex items-center space-x-1';

  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'text-gray-400 hover:text-red-600 p-2 rounded-full hover:bg-red-50 transition-colors';
  deleteBtn.title = "Delete";
  deleteBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>`;
  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    handleDelete(r);
  });
  rightActions.appendChild(deleteBtn);

  footer.appendChild(rightActions);
  card.appendChild(footer);

  return card;
}

function renderStars(n) {
  const full = Math.max(0, Math.min(5, parseInt(n, 10) || 0));
  let out = '';
  for (let i = 0; i < 5; i++) {
    const color = i < full ? 'text-yellow-400' : 'text-gray-300';
    out += `<svg class="w-5 h-5 ${color}" fill="currentColor"><use href="#icon-star"/></svg>`;
  }
  return out;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>\"]/g, s => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[s]));
}

function updateFormWishlistUI() {
  const buttons = document.querySelectorAll('#form-wishlist-buttons .wishlist-toggle-button');
  buttons.forEach(btn => {
    if ((btn.dataset.value === 'true') === formWishlisted) {
      btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.remove('hover:bg-gray-50', 'bg-indigo-600', 'text-white');
    } else {
      btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300', 'bg-indigo-600', 'text-white');
      btn.classList.add('hover:bg-gray-50');
    }
  });
  const ratingSection = document.getElementById('rating-section');
  if (ratingSection) ratingSection.classList.toggle('hidden', formWishlisted);
}

function openMarkVisitedModal(r, fromEditModal) {
  restaurantToMarkVisited = r;
  markVisitedFromEditModal = fromEditModal;
  const modal = document.getElementById('mark-visited-modal');
  if (modal) modal.classList.remove('hidden');
  const stars = document.getElementById('mark-visited-stars');
  if (stars) {
    stars.dataset.rating = '5';
    updateMarkVisitedStars();
  }
}

function closeMarkVisitedModal() {
  const modal = document.getElementById('mark-visited-modal');
  if (modal) modal.classList.add('hidden');
  restaurantToMarkVisited = null;
}

function applyStarRating(starsEl) {
  const rating = parseInt(starsEl.dataset.rating, 10);
  Array.from(starsEl.children).forEach((star, i) => {
    star.classList.toggle('text-yellow-400', i < rating);
    star.classList.toggle('text-gray-300', i >= rating);
  });
}

function updateMarkVisitedStars() {
  const stars = document.getElementById('mark-visited-stars');
  if (stars) applyStarRating(stars);
}

// Make edit helpers global so card buttons can call them
function enterEditMode(r) {
  const modal = document.getElementById('restaurant-modal');
  if (modal) modal.classList.remove('hidden');
  const fab = document.getElementById('add-restaurant-btn-fab');
  fab.classList.add('hidden');
  const title = document.getElementById('modal-title');
  if (title) title.textContent = 'Restaurant';

  const refreshBtn = document.getElementById('refresh-restaurant-btn');
  if (refreshBtn) refreshBtn.classList.remove('hidden');

  const placeAutocomplete = document.getElementById('place-autocomplete');
  const nameDisplay = document.getElementById('edit-name-display');

  if (placeAutocomplete) placeAutocomplete.classList.add('hidden');
  if (nameDisplay) {
    nameDisplay.textContent = r.name || '';
    nameDisplay.classList.remove('hidden');
  }

  // update type buttons
  selectedDiningOptions = r.diningOptions; // Sync global state
  const typeButtons = document.querySelectorAll('#dining-options-buttons .dining-options-button');
  typeButtons.forEach(btn => {
    if (btn.dataset.value === r.diningOptions) {
      btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
      btn.classList.remove('hover:bg-gray-50', 'bg-indigo-600', 'text-white');
    } else {
      btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300', 'bg-indigo-600', 'text-white');
      btn.classList.add('hover:bg-gray-50');
    }
  });

  const ratingStars = document.getElementById('rating-stars');
  if (ratingStars) {
    ratingStars.dataset.rating = String(Number(r.rating) || 0);
    applyStarRating(ratingStars);
  }

  const notesInput = document.getElementById('restaurant-notes');
  if (notesInput) {
    notesInput.value = r.notes || '';
  }

  // Load Dishes
  // deep copy to avoid mutations affecting cache before save
  currentDishes = (r.dishes || []).map(d => ({ ...d }));
  renderDishesList();

  displayAddress(r.address);
  displayOpeningHours(r.openingHours);

  document.getElementById('edit-id').value = r.id;
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.textContent = 'Save changes';
    submitBtn.disabled = false;
    submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
  }

  // Wishlisted state: hide toggle, show/hide rating and mark-visited button
  document.getElementById('wishlist-toggle-section')?.classList.add('hidden');
  document.getElementById('modal-mark-visited-section')?.classList.toggle('hidden', !r.wishlisted);
  document.getElementById('rating-section')?.classList.toggle('hidden', r.wishlisted);

  document.body.classList.add('overflow-hidden');
}

function closeModal() {
  const form = document.getElementById('restaurant-form');
  if (form) form.reset();

  const refreshBtn = document.getElementById('refresh-restaurant-btn');
  if (refreshBtn) refreshBtn.classList.add('hidden');

  const placeAutocomplete = document.getElementById('place-autocomplete');
  const nameDisplay = document.getElementById('edit-name-display');

  if (placeAutocomplete) {
    placeAutocomplete.value = '';
    placeAutocomplete.classList.remove('pointer-events-none', 'opacity-50', 'hidden');
  }
  if (nameDisplay) {
    nameDisplay.textContent = '';
    nameDisplay.classList.add('hidden');
  }

  const modal = document.getElementById('restaurant-modal');
  if (modal) modal.classList.add('hidden');
  document.body.classList.remove('overflow-hidden');
  const fab = document.getElementById('add-restaurant-btn-fab');
  if (restaurantsCache.filter(r => r.wishlisted === activeWishlistFilter).length > 0) {
    fab.classList.remove('hidden');
  }
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
  selectedDiningOptions = 'both';
  const typeButtons = document.querySelectorAll('#dining-options-buttons .dining-options-button');
  typeButtons.forEach(btn => {
    if (btn.dataset.value === 'both') {
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
    applyStarRating(ratingStars);
  }

  const notesInput = document.getElementById('restaurant-notes');
  if (notesInput) {
    notesInput.value = '';
  }

  displayAddress(null);
  displayOpeningHours(null);
  clearMessage();

  // Reset dishes
  currentDishes = [];
  renderDishesList();
  resetDishForm();
}

function updateDishRatingUI(rating) {
  newDishRating = rating;
  const upBtn = document.getElementById('dish-rating-up');
  const downBtn = document.getElementById('dish-rating-down');

  if (rating === 1) {
    upBtn.classList.add('text-green-600', 'bg-green-50');
    upBtn.classList.remove('text-gray-400');
    downBtn.classList.remove('text-red-600', 'bg-red-50');
    downBtn.classList.add('text-gray-400');
  } else {
    upBtn.classList.remove('text-green-600', 'bg-green-50');
    upBtn.classList.add('text-gray-400');
    downBtn.classList.add('text-red-600', 'bg-red-50');
    downBtn.classList.remove('text-gray-400');
  }
}

function resetDishForm() {
  document.getElementById('add-dish-form').classList.add('hidden');
  document.getElementById('add-dish-btn').classList.remove('hidden');
  document.getElementById('new-dish-name').value = '';
  document.getElementById('new-dish-notes').value = '';

  // Reset radio to "Good"
  const radioGood = document.querySelector('input[name="new-dish-rating"][value="1"]');
  if (radioGood) radioGood.checked = true;

  editingDishIndex = -1;
}

function renderDishesList() {
  const container = document.getElementById('dishes-container');
  container.innerHTML = '';

  currentDishes.forEach((dish, index) => {
    const dishEl = document.createElement('div');
    dishEl.className = 'bg-gray-50 rounded border border-gray-100 group';

    // Inline Edit Mode
    if (index === editingDishIndex) {
      dishEl.classList.add('p-3');
      dishEl.innerHTML = `
                <div class="space-y-3">
                    <div class="space-y-2">
                        <input type="text" id="edit-dish-name-${index}" value="${dish.name.replace(/"/g, '&quot;')}" class="block w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 shadow-sm" placeholder="Dish name">
                        <textarea id="edit-dish-notes-${index}" rows="2" class="block w-full text-sm border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 shadow-sm" placeholder="Notes">${(dish.notes || '').replace(/</g, '&lt;')}</textarea>
                    </div>
                    <div class="flex items-center justify-between">
                         <div class="flex gap-4">
                            <label class="cursor-pointer">
                                <input type="radio" name="edit-rating-${index}" value="1" ${dish.rating === 1 ? 'checked' : ''} class="peer sr-only">
                                <div class="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 peer-checked:text-green-700 peer-checked:bg-green-100 transition-all">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                        <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                                    </svg>
                                </div>
                            </label>
                            <label class="cursor-pointer">
                                <input type="radio" name="edit-rating-${index}" value="0" ${dish.rating !== 1 ? 'checked' : ''} class="peer sr-only">
                                <div class="p-1.5 rounded-md hover:bg-gray-100 text-gray-400 peer-checked:text-red-700 peer-checked:bg-red-100 transition-all">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                        <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
                                    </svg>
                                </div>
                            </label>
                         </div>
                         <div class="flex gap-2">
                            <button onclick="saveEdit(${index})" type="button" class="inline-flex items-center px-2.5 py-1.5 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">Save</button>
                            <button onclick="cancelEdit()" type="button" class="inline-flex items-center px-2.5 py-1.5 border border-gray-300 text-xs font-medium rounded text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">Cancel</button>
                         </div>
                    </div>
                </div>
            `;
    } else {
      // Normal Display
      dishEl.classList.add('flex', 'items-start', 'justify-between', 'p-2');

      const contentDiv = document.createElement('div');
      contentDiv.className = 'flex-1 min-w-0 mr-2';

      const headerDiv = document.createElement('div');
      headerDiv.className = 'flex items-center gap-2';

      const ratingIcon = document.createElement('span');
      ratingIcon.className = 'shrink-0 mt-0.5'; // Align slightly
      if (dish.rating === 1) {
        // Soft Green Badge
        ratingIcon.innerHTML = `
                <div class="p-1 rounded-md bg-green-100 text-green-700">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                    </svg>
                </div>`;
      } else {
        // Soft Red Badge
        ratingIcon.innerHTML = `
                <div class="p-1 rounded-md bg-red-100 text-red-700">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z" />
                    </svg>
                </div>`;
      }

      const nameSpan = document.createElement('span');
      nameSpan.className = 'text-sm font-medium text-gray-900 truncate';
      nameSpan.textContent = dish.name;

      headerDiv.appendChild(ratingIcon);
      headerDiv.appendChild(nameSpan);
      contentDiv.appendChild(headerDiv);

      if (dish.notes) {
        const notesP = document.createElement('p');
        notesP.className = 'text-xs text-gray-500 mt-0.5 truncate';
        notesP.textContent = dish.notes;
        contentDiv.appendChild(notesP);
      }

      dishEl.appendChild(contentDiv);

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'dish-actions flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity';

      const editBtn = document.createElement('button');
      editBtn.type = 'button';
      editBtn.className = 'p-1.5 text-gray-400 hover:text-indigo-600 rounded-md hover:bg-gray-100';
      editBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>`;
      editBtn.onclick = () => editDish(index);

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'p-1.5 text-gray-400 hover:text-red-600 rounded-md hover:bg-gray-100';
      deleteBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>`;
      deleteBtn.onclick = () => deleteDish(index);

      actionsDiv.appendChild(editBtn);
      actionsDiv.appendChild(deleteBtn);
      dishEl.appendChild(actionsDiv);

    } // End Else

    container.appendChild(dishEl);
  });
}

function editDish(index) {
  // Hide global add form first
  document.getElementById('add-dish-form').classList.add('hidden');
  document.getElementById('add-dish-btn').classList.remove('hidden');
  document.getElementById('save-dish-btn').textContent = 'Add';

  editingDishIndex = index;
  renderDishesList();
}

function saveEdit(index) {
  const nameInput = document.getElementById(`edit-dish-name-${index}`);
  const notesInput = document.getElementById(`edit-dish-notes-${index}`);
  const ratingRadio = document.querySelector(`input[name="edit-rating-${index}"]:checked`);

  if (!nameInput || !ratingRadio) return;

  const name = nameInput.value.trim();
  const notes = notesInput.value.trim();
  const rating = parseInt(ratingRadio.value);

  if (!name) {
    nameInput.focus();
    return;
  }

  currentDishes[index] = { ...currentDishes[index], name, rating, notes };
  editingDishIndex = -1;
  renderDishesList();
}

function cancelEdit() {
  editingDishIndex = -1;
  renderDishesList();
}

function deleteDish(index) {
  currentDishes.splice(index, 1);
  renderDishesList();
}

function showMessage(msg, isError = false) {
  const el = document.getElementById('message');
  el.className = 'text-sm text-center pt-2 h-6 ' + (isError ? 'text-red-600' : 'text-green-600');
  el.textContent = msg;
  setTimeout(() => { el.textContent = '' }, 3000);
}

function clearMessage() {
  const el = document.getElementById('message');
  el.textContent = '';
}

// Delete Modal Logic
let restaurantToDelete = null;

function handleDelete(r) {
  if (!r || !r.id) return;
  restaurantToDelete = r;
  const deleteModal = document.getElementById('delete-modal');
  if (deleteModal) deleteModal.classList.remove('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('restaurant-modal');
  const addBtn = document.getElementById('add-restaurant-btn');
  const closeBtn = document.getElementById('close-modal-btn');
  const typeButtonsContainer = document.getElementById('dining-options-buttons');
  const ratingStarsContainer = document.getElementById('rating-stars');

  // Type selection
  // selectedDiningOptions is global
  if (typeButtonsContainer) {
    typeButtonsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.dining-options-button');
      if (!btn) return;
      selectedDiningOptions = btn.dataset.value;
      updateTypeButtons();
    });
  }

  function updateTypeButtons() {
    typeButtonsContainer.querySelectorAll('.dining-options-button').forEach(btn => {
      if (btn.dataset.value === selectedDiningOptions) {
        btn.classList.add('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300');
        btn.classList.remove('hover:bg-gray-50', 'bg-indigo-600', 'text-white');
      } else {
        btn.classList.remove('bg-white', 'shadow-sm', 'ring-1', 'ring-inset', 'ring-gray-300', 'bg-indigo-600', 'text-white');
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
    applyStarRating(ratingStarsContainer);
  }

  const form = document.getElementById('restaurant-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      // Get data from the global variable set by autocomplete
      const newPlaceData = window.selectedPlaceData || {};
      const name = newPlaceData.name;
      const address = newPlaceData.address;
      const city = newPlaceData.city;
      const id = newPlaceData.id;
      const mapUri = newPlaceData.mapUri;
      const directionsUri = newPlaceData.directionsUri;
      const priceLevel = newPlaceData.priceLevel;
      const openingHours = newPlaceData.openingHours;
      const types = newPlaceData.types;
      const latitude = newPlaceData.latitude ?? null;
      const longitude = newPlaceData.longitude ?? null;
      const editId = document.getElementById('edit-id').value;
      const notes = document.getElementById('restaurant-notes')?.value || '';
      const diningOptions = selectedDiningOptions;
      const rating = ratingStarsContainer.dataset.rating;
      const dishes = currentDishes;
      try {
        let res;
        if (editId) {
          const payload = { diningOptions, notes, dishes };
          if (rating !== '0') payload.rating = rating;
          res = await fetch(`/api/restaurants/${editId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify(payload)
          });
        } else {
          const payload = { id, name, address, city, diningOptions, mapUri, directionsUri, priceLevel, notes, dishes, openingHours, types, latitude, longitude, wishlisted: formWishlisted };
          if (!formWishlisted) payload.rating = rating;
          res = await fetch('/api/restaurants', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify(payload)
          });
        }
        if (!res.ok) {
          const err = await res.json();
          showMessage(err.error || 'Failed to save', true);
        } else {
          const saved = await res.json();
          if (editId) {
            const idx = restaurantsCache.findIndex(r => r.id === editId);
            if (idx !== -1) restaurantsCache[idx] = saved;
          } else {
            restaurantsCache.unshift(saved);
          }
          closeModal();
          populateCityFilter();
          populateCuisineFilter();
          filterAndRender();
        }
      } catch (err) {
        showMessage('Something went wrong', true);
      }
    });
  } else {
    console.warn('restaurant-form not found');
  }
  // wire up filters
  const searchInput = document.getElementById('search-input');
  if (searchInput) searchInput.addEventListener('input', filterAndRender);

  // Re-render on resize so column count stays correct
  let lastColCount = window.innerWidth >= 1024 ? 3 : window.innerWidth >= 640 ? 2 : 1;
  window.addEventListener('resize', () => {
    const newColCount = window.innerWidth >= 1024 ? 3 : window.innerWidth >= 640 ? 2 : 1;
    if (newColCount !== lastColCount) {
      lastColCount = newColCount;
      filterAndRender();
    }
  });

  // Modal handling
  const fab = document.getElementById('add-restaurant-btn-fab');
  const openModal = () => {
    modal.classList.remove('hidden');
    document.body.classList.add('overflow-hidden');
    fab.classList.add('hidden');
    document.getElementById('modal-mark-visited-section')?.classList.add('hidden');
    document.getElementById('rating-section')?.classList.remove('hidden');
    document.getElementById('wishlist-toggle-section')?.classList.remove('hidden');
    formWishlisted = activeWishlistFilter;
    updateFormWishlistUI();
  };
  addBtn.addEventListener('click', openModal);
  fab.addEventListener('click', openModal);
  closeBtn.addEventListener('click', closeModal);
  // Close modal on outside click
  window.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  loadRestaurants();

  // Dishes UI Logic
  const addDishBtn = document.getElementById('add-dish-btn');
  const addDishForm = document.getElementById('add-dish-form');
  const cancelDishBtn = document.getElementById('cancel-dish-btn');
  const saveDishBtn = document.getElementById('save-dish-btn');
  const dishRatingUp = document.getElementById('dish-rating-up');
  const dishRatingDown = document.getElementById('dish-rating-down');

  if (addDishBtn) {
    addDishBtn.addEventListener('click', () => {
      resetDishForm();
      addDishForm.classList.remove('hidden');
      addDishBtn.classList.add('hidden');
      document.getElementById('new-dish-name').focus();
    });
  }

  if (cancelDishBtn) {
    cancelDishBtn.addEventListener('click', () => {
      resetDishForm();
    });
  }

  if (saveDishBtn) {
    saveDishBtn.addEventListener('click', () => {
      const nameInput = document.getElementById('new-dish-name');
      const notesInput = document.getElementById('new-dish-notes');

      const name = nameInput.value.trim();
      const notes = notesInput.value.trim();
      const ratingRadio = document.querySelector(`input[name="new-dish-rating"]:checked`);
      const rating = ratingRadio ? parseInt(ratingRadio.value) : 1;

      if (!name) {
        nameInput.focus();
        return;
      }

      // Add new dish
      currentDishes.push({ name, rating, notes });

      renderDishesList();
      resetDishForm();
    });
  }

  if (dishRatingUp) {
    dishRatingUp.addEventListener('click', () => updateDishRatingUI(1));
  }
  if (dishRatingDown) {
    dishRatingDown.addEventListener('click', () => updateDishRatingUI(0));
  }

  // Dropdown Toggles using Event Delegation
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('.dropdown-trigger');
    if (trigger) {
      const currentMenu = trigger.nextElementSibling;
      // Close others
      document.querySelectorAll('.dropdown-menu').forEach(menu => {
        if (menu !== currentMenu) menu.classList.add('hidden');
      });
      currentMenu.classList.toggle('hidden');
      return;
    }

    // Option Click
    const optionBtn = e.target.closest('.dropdown-menu button');
    if (optionBtn) {
      const menu = optionBtn.closest('.dropdown-menu');
      const container = menu.parentElement;
      const trigger = container.querySelector('.dropdown-trigger');
      const newLabel = optionBtn.dataset.label || optionBtn.textContent;
      const labelSpan = trigger.querySelector('.sort-label, .filter-label');
      if (labelSpan) labelSpan.innerHTML = newLabel;
      const input = container.querySelector('input[type="hidden"]');
      if (input) input.value = optionBtn.dataset.value;
      const isActive = optionBtn.dataset.value !== '';
      setTriggerActive(trigger, isActive);

      menu.classList.add('hidden');
      filterAndRender();
      return;
    }

    // Click Outside
    if (!e.target.closest('.filter-dropdown') && !e.target.closest('.sort-dropdown')) {
      document.querySelectorAll('.dropdown-menu').forEach(menu => menu.classList.add('hidden'));
    }
  });

  // Close dropdowns on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.dropdown-menu').forEach(menu => menu.classList.add('hidden'));
    }
  });

  // Clear filters button at the top
  const topClearBtn = document.getElementById('top-clear-filters-btn');
  if (topClearBtn) topClearBtn.addEventListener('click', clearFilters);

  // View toggle
  const viewListBtn = document.getElementById('view-list-btn');
  const viewMapBtn = document.getElementById('view-map-btn');
  if (viewListBtn) viewListBtn.addEventListener('click', () => setView('list'));
  if (viewMapBtn) viewMapBtn.addEventListener('click', () => setView('map'));

  // Wishlist pills
  const pillVisited = document.getElementById('pill-visited');
  const pillWantToGo = document.getElementById('pill-want-to-go');

  function updatePills() {
    if (!pillVisited || !pillWantToGo) return;
    if (activeWishlistFilter) {
      pillVisited.className = 'px-4 py-1.5 rounded-full text-sm font-medium transition-all text-gray-500 hover:text-gray-700';
      pillWantToGo.className = 'px-4 py-1.5 rounded-full text-sm font-medium transition-all bg-indigo-600 text-white';
    } else {
      pillVisited.className = 'px-4 py-1.5 rounded-full text-sm font-medium transition-all bg-indigo-600 text-white';
      pillWantToGo.className = 'px-4 py-1.5 rounded-full text-sm font-medium transition-all text-gray-500 hover:text-gray-700';
    }
  }

  const ratingFilterContainer = document.getElementById('rating-filter-container');
  const ratingSortOption = document.querySelector('.sort-dropdown [data-value="rating"]');
  const sortInput = document.getElementById('current-sort');
  const sortTrigger = document.querySelector('.sort-dropdown .dropdown-trigger');

  if (pillVisited) {
    pillVisited.addEventListener('click', () => {
      activeWishlistFilter = false;
      // !hidden (Tailwind v4 important modifier) is used instead of hidden because
      // the container also has inline-block, which would otherwise win in the CSS
      // cascade over the layered .hidden utility.
      ratingFilterContainer?.classList.remove('!hidden');
      ratingSortOption?.classList.remove('hidden');
      updatePills();
      populateCityFilter();
      populateCuisineFilter();
      filterAndRender();
    });
  }
  if (pillWantToGo) {
    pillWantToGo.addEventListener('click', () => {
      activeWishlistFilter = true;
      ratingFilterContainer?.classList.add('!hidden');
      ratingSortOption?.classList.add('hidden');
      if (sortInput?.value === 'rating') {
        sortInput.value = '';
        const sortLabel = sortTrigger?.querySelector('.sort-label');
        if (sortLabel) sortLabel.innerHTML = sortTrigger.dataset.default;
        setTriggerActive(sortTrigger, false);
      }
      updatePills();
      populateCityFilter();
      populateCuisineFilter();
      filterAndRender();
    });
  }
  updatePills();

  // Refresh Restaurant Button
  const refreshBtn = document.getElementById('refresh-restaurant-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async (e) => {
      e.preventDefault();

      const editId = document.getElementById('edit-id').value;

      if (!editId) return;

      const icon = refreshBtn.querySelector('svg');
      icon.classList.add('animate-spin');

      try {
        // Fetch fresh data
        const place = new google.maps.places.Place({ id: editId });
        await place.fetchFields({
          fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'googleMapsLinks', 'googleMapsURI', 'types', 'priceLevel', 'regularOpeningHours', 'utcOffsetMinutes'],
        });

        const name = place.displayName;
        const address = place.formattedAddress;
        const mapUri = place.googleMapsLinks?.placeURI || place.googleMapsURI;
        const directionsUri = place.googleMapsLinks?.directionsURI;

        const city = getCity(place);

        const priceLevel = getPriceLevel(place);

        const openingHours = getOpeningHours(place);

        const types = place.types || [];

        const latitude = place.location?.lat() ?? null;
        const longitude = place.location?.lng() ?? null;

        // Send update to backend
        const res = await fetch(`/api/restaurants/${editId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({
            name, address, city, mapUri, directionsUri, priceLevel, openingHours, types, latitude, longitude
          })
        });

        if (res.ok) {
          const updated = await res.json();
          const idx = restaurantsCache.findIndex(r => r.id === editId);
          if (idx !== -1) restaurantsCache[idx] = updated;
          populateCityFilter();
          populateCuisineFilter();
          filterAndRender();
          enterEditMode(updated);
          showMessage('Refreshed Google Maps data successfully');
        } else {
          showMessage('Failed to refresh Google Maps data', true);
        }

      } catch (err) {
        console.error('Refresh failed', err);
        showMessage('Refresh failed: ' + err.message, true);
      } finally {
        icon.classList.remove('animate-spin');
      }
    });
  }

  // Delete Modal
  const deleteModal = document.getElementById('delete-modal');
  const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
  const cancelDeleteBtn = document.getElementById('cancel-delete-btn');

  if (confirmDeleteBtn) {
    confirmDeleteBtn.addEventListener('click', async () => {
      if (!restaurantToDelete) return;

      try {
        const res = await fetch(`/api/restaurants/${restaurantToDelete.id}`, { method: 'DELETE', headers: { 'X-CSRFToken': csrfToken() } });
        if (res.ok) {
          restaurantsCache = restaurantsCache.filter(r => r.id !== restaurantToDelete.id);

          // If the deleted restaurant was the only one in its city/cuisine, we need to update filters before rendering.
          populateCityFilter();
          populateCuisineFilter();
          filterAndRender();
        } else {
          alert('Failed to delete restaurant.');
        }
      } catch (error) {
        alert('Failed to delete restaurant.');
      }

      if (deleteModal) deleteModal.classList.add('hidden');
      restaurantToDelete = null;
    });
  }

  if (cancelDeleteBtn) {
    cancelDeleteBtn.addEventListener('click', () => {
      if (deleteModal) deleteModal.classList.add('hidden');
      restaurantToDelete = null;
    });
  }

  // Close delete modal on outside click
  window.addEventListener('click', (e) => {
    if (e.target === deleteModal) {
      deleteModal.classList.add('hidden');
      restaurantToDelete = null;
    }
  });

  // Mark as Visited Modal
  const markVisitedModal = document.getElementById('mark-visited-modal');
  const markVisitedStarsEl = document.getElementById('mark-visited-stars');
  const confirmMarkVisitedBtn = document.getElementById('confirm-mark-visited-btn');
  const cancelMarkVisitedBtn = document.getElementById('cancel-mark-visited-btn');
  const modalMarkVisitedBtn = document.getElementById('modal-mark-visited-btn');

  if (markVisitedStarsEl) {
    markVisitedStarsEl.addEventListener('click', (e) => {
      const star = e.target.closest('svg');
      if (!star) return;
      const rating = Array.from(markVisitedStarsEl.children).indexOf(star) + 1;
      markVisitedStarsEl.dataset.rating = String(rating);
      updateMarkVisitedStars();
    });
  }

  if (modalMarkVisitedBtn) {
    modalMarkVisitedBtn.addEventListener('click', () => {
      const editId = document.getElementById('edit-id').value;
      const r = restaurantsCache.find(r => r.id === editId);
      if (r) openMarkVisitedModal(r, true);
    });
  }

  if (confirmMarkVisitedBtn) {
    confirmMarkVisitedBtn.addEventListener('click', async () => {
      if (!restaurantToMarkVisited) return;
      const rating = parseInt(document.getElementById('mark-visited-stars').dataset.rating, 10);
      try {
        const res = await fetch(`/api/restaurants/${restaurantToMarkVisited.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
          body: JSON.stringify({ wishlisted: false, rating })
        });
        if (res.ok) {
          const updated = await res.json();
          const idx = restaurantsCache.findIndex(r => r.id === restaurantToMarkVisited.id);
          if (idx !== -1) restaurantsCache[idx] = updated;
          closeMarkVisitedModal();
          if (markVisitedFromEditModal) closeModal();
          populateCityFilter();
          populateCuisineFilter();
          filterAndRender();
        } else {
          showMessage('Failed to mark as visited', true);
        }
      } catch (err) {
        showMessage('Something went wrong', true);
      }
    });
  }

  if (cancelMarkVisitedBtn) {
    cancelMarkVisitedBtn.addEventListener('click', closeMarkVisitedModal);
  }

  if (markVisitedModal) {
    window.addEventListener('click', (e) => {
      if (e.target === markVisitedModal) closeMarkVisitedModal();
    });
  }

  // Wishlist toggle in add form
  const formWishlistButtons = document.getElementById('form-wishlist-buttons');
  if (formWishlistButtons) {
    formWishlistButtons.addEventListener('click', (e) => {
      const btn = e.target.closest('.wishlist-toggle-button');
      if (!btn) return;
      formWishlisted = btn.dataset.value === 'true';
      updateFormWishlistUI();
    });
  }

  // Share target handling
  (async () => {
    const restaurantInfo = window.RESTAURANT_INFO;
    if (!restaurantInfo) return;

    openModal();
    const placeAutocomplete = document.getElementById('place-autocomplete');

    try {
      // Wait for the Maps JS API to finish loading
      await new Promise(resolve => {
        (function check() {
          if (window.google?.maps?.places?.Place?.searchByText) resolve();
          else setTimeout(check, 100);
        })();
      });

      await allowedTypesReady;

      const { places } = await google.maps.places.Place.searchByText({
        textQuery: restaurantInfo,
        fields: ['displayName', 'formattedAddress', 'location', 'addressComponents', 'googleMapsLinks', 'googleMapsURI', 'types', 'priceLevel', 'regularOpeningHours', 'utcOffsetMinutes'],
        maxResultCount: 1,
      });

      if (!places || places.length === 0) {
        showMessage('Could not find restaurant', true);
        return;
      }

      await selectPlaceInForm(places[0]);
    } catch (err) {
      console.error('[Share Target] Error:', err);
      showMessage('Could not find restaurant', true);
    }
  })();
});

