# Add Caching for Airbnb and Holidify Requests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add caching mechanisms to the Airbnb and Holidify fetch functions to improve performance and reliability by reducing redundant HTTP requests, following the existing pattern used for Google Trends caching.

**Architecture:** Extend the existing caching pattern by creating two new cache dictionaries (_AIRBNB_CACHE and _HOLIDIFY_CACHE) with corresponding TTL constants, and modify the fetch_airbnb_comps and fetch_event_spike functions to check these caches before making HTTP requests.

**Tech Stack:** Python, requests, BeautifulSoup, datetime, typing

---

### Task 1: Add Airbnb cache constants

**Files:**
- Modify: `pilgrim_pulse.py:40-42` (add after existing cache constants)

- [ ] **Step 1: Write the failing test**

Since this is adding constants, we'll test by verifying the constants exist and have correct values after implementation.

- [ ] **Step 2: Run test to verify it fails**

We'll verify the constants don't exist yet by attempting to import and check for them.

Run: `python3 -c "import pilgrim_pulse; print(hasattr(pilgrim_pulse, '_AIRBNB_CACHE'))"`
Expected: False

- [ ] **Step 3: Write minimal implementation**

```python
# Simple in‑memory cache for Airbnb responses to avoid hammering the service
_AIRBNB_CACHE: Dict[str, Tuple[Dict[str, float], float]] = {}  # city-check_in-check_out -> (data, timestamp)
_AIRBNB_CACHE_TTL = 6 * 60 * 60  # 6 hours
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -c "import pilgrim_pulse; print(hasattr(pilgrim_pulse, '_AIRBNB_CACHE'))"`
Expected: True

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "feat: add Airbnb cache constants"
```

### Task 2: Add Holidify cache constants

**Files:**
- Modify: `pilgrim_pulse.py:45-47` (add after Airbnb cache constants)

- [ ] **Step 1: Write the failing test**

Run: `python3 -c "import pilgrim_pulse; print(hasattr(pilgrim_pulse, '_HOLIDIFY_CACHE'))"`
Expected: False

- [ ] **Step 2: Run test to verify it fails**

Same as above - verify constant doesn't exist.

- [ ] **Step 3: Write minimal implementation**

```python
# Simple in‑memory cache for Holidify responses to avoid hammering the service
_HOLIDIFY_CACHE: Dict[str, Tuple[float, float]] = {}  # city-start_date-end_date -> (multiplier, timestamp)
_HOLIDIFY_CACHE_TTL = 6 * 60 * 60  # 6 hours
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -c "import pilgrim_pulse; print(hasattr(pilgrim_pulse, '_HOLIDIFY_CACHE'))"`
Expected: True

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "feat: add Holidify cache constants"
```

### Task 3: Implement caching in fetch_airbnb_comps function

**Files:**
- Modify: `pilgrim_pulse.py:48-107` (the fetch_airbnb_comps function)

- [ ] **Step 1: Write the failing test**

We'll create a test that calls the function twice with same parameters and verifies HTTP is only called once.

```python
import time
from unittest.mock import patch
import pilgrim_pulse

def test_airbnb_caching():
    city = "testcity"
    check_in = pilgrim_pulse.dt.date.today()
    check_out = check_in + pilgrim_pulse.dt.timedelta(days=2)
    
    # Clear cache
    pilgrim_pulse._AIRBNB_CACHE.clear()
    
    # Mock requests.get to track calls
    with patch('pilgrim_pulse.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>₹1000 1 stays</html>'
        
        # First call
        result1 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        first_call_count = mock_get.call_count
        
        # Second call with same params
        result2 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        second_call_count = mock_get.call_count
        
        # Should only have made one HTTP request
        assert second_call_count == first_call_count == 1
        assert result1 == result2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest <(cat <<'EOF'
import time
from unittest.mock import patch
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_airbnb_caching():
    city = "testcity"
    check_in = pilgrim_pulse.dt.date.today()
    check_out = check_in + pilgrim_pulse.dt.timedelta(days=2)
    
    # Clear cache
    pilgrim_pulse._AIRBNB_CACHE.clear()
    
    # Mock requests.get to track calls
    with patch('pilgrim_pulse.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>₹1000 1 stays</html>'
        
        # First call
        result1 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        first_call_count = mock_get.call_count
        
        # Second call with same params
        result2 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        second_call_count = mock_get.call_count
        
        # Should only have made one HTTP request
        assert second_call_count == first_call_count == 1
        assert result1 == result2

if __name__ == "__main__":
    test_airbnb_caching()
    print("Test passed!")
EOF
) -v`
Expected: FAIL (function not implemented yet)

- [ ] **Step 3: Write minimal implementation**

Modify the fetch_airbnb_comps function to add caching logic:

```python
def fetch_airbnb_comps(city: str, check_in: dt.date, check_out: dt.date) -> Dict[str, float]:
    """
    Scrape Airbnb search results for the given city and date range.
    Returns a dict with:
        - avg_price: average nightly price (INR) derived from all price strings found.
        - occupancy: estimated occupancy % = (number of price strings / total stays) * 100,
                     capped at 100.
    """
    # Create cache key
    cache_key = f"{city.lower()}-{check_in.isoformat()}-{check_out.isoformat()}"
    now = time.time()
    
    # Check cache first
    if cache_key in _AIRBNB_CACHE:
        data, timestamp = _AIRBNB_CACHE[cache_key]
        if now - timestamp < _AIRBNB_CACHE_TTL:
            return data
    
    # Build the search URL
    cin = check_in.strftime("%Y-%m-%d")
    cout = check_out.strftime("%Y-%m-%d")
    url = (
        f"https://www.airbnb.com/s/{city}/homes?"
        f"checkin={cin}&checkout={cout}&adults=1&source=bb&ss_id="
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️  Airbnb request failed ({e}); using fallback values.", file=sys.stderr)
        result = {"avg_price": 1500.0, "occupancy": 65.0}
        # Cache the fallback result too
        _AIRBNB_CACHE[cache_key] = (result, now)
        return result

    html = resp.text

    # --- 1️⃣ Extract all price strings (₹1,200, $45, etc.) -------------------------
    price_matches = re.findall(r"[₹$]\s?[\d,]+", html)
    prices = []
    for m in price_matches:
        # strip currency symbol and commas
        num = re.sub(r"[₹$,\s]", "", m)
        if num.isdigit():
            prices.append(int(num))
        elif re.fullmatch(r"\d+\.\d+", num):
            try:
                prices.append(float(num))
            except ValueError:
                pass

    # --- 2️⃣ Extract total number of stays/results -------------------------------
    # Airbnb often shows text like “1,000 stays” or “1,200 results”.
    total_match = re.search(r"([\d,]+)\s+(?:stays|results|homes)", html, re.I)
    total_listings = 0
    if total_match:
        total_str = total_match.group(1).replace(",", "")
        if total_str.isdigit():
            total_listings = int(total_str)

    # If we couldn't get a total, fall back to a reasonable baseline
    if total_listings == 0:
        total_listings = max(len(prices), 1)

    # --- 3️⃣ Compute average price & occupancy ----------------------------------
    avg_price = sum(prices) / len(prices) if prices else 1500.0
    occupancy = (len(prices) / total_listings) * 100 if total_listings else 65.0
    occupancy = max(0.0, min(100.0, occupancy))

    # Clamp price to a sane range (avoid crazy outliers)
    avg_price = max(0.0, min(10000.0, avg_price))

    result = {"avg_price": round(avg_price, 2), "occupancy": round(occupancy, 2)}
    
    # Store in cache
    _AIRBNB_CACHE[cache_key] = (result, now)
    
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest <(cat <<'EOF'
import time
from unittest.mock import patch
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_airbnb_caching():
    city = "testcity"
    check_in = pilgrim_pulse.dt.date.today()
    check_out = check_in + pilgrim_pulse.dt.timedelta(days=2)
    
    # Clear cache
    pilgrim_pulse._AIRBNB_CACHE.clear()
    
    # Mock requests.get to track calls
    with patch('pilgrim_pulse.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>₹1000 1 stays</html>'
        
        # First call
        result1 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        first_call_count = mock_get.call_count
        
        # Second call with same params
        result2 = pilgrim_pulse.fetch_airbnb_comps(city, check_in, check_out)
        second_call_count = mock_get.call_count
        
        # Should only have made one HTTP request
        assert second_call_count == first_call_count == 1
        assert result1 == result2

if __name__ == "__main__":
    test_airbnb_caching()
    print("Test passed!")
EOF
) -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "feat: implement caching in fetch_airbnb_comps function"
```

### Task 4: Implement caching in fetch_event_spike function

**Files:**
- Modify: `pilgrim_pulse.py:113-147` (the fetch_event_spike function)

- [ ] **Step 1: Write the failing test**

```python
import time
from unittest.mock import patch
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_holidify_caching():
    city = "testcity"
    start_date = pilgrim_pulse.dt.date.today()
    end_date = start_date + pilgrim_pulse.dt.timedelta(days=2)
    
    # Clear cache
    pilgrim_pulse._HOLIDIFY_CACHE.clear()
    
    # Mock requests.get to track calls
    with patch('pilgrim_pulse.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>Jan 15, 2026</html>'  # Date within range
        
        # First call
        result1 = pilgrim_pulse.fetch_event_spike(city, start_date, end_date)
        first_call_count = mock_get.call_count
        
        # Second call with same params
        result2 = pilgrim_pulse.fetch_event_spike(city, start_date, end_date)
        second_call_count = mock_get.call_count
        
        # Should only have made one HTTP request
        assert second_call_count == first_call_count == 1
        assert result1 == result2 == 1.5  # Should return event multiplier

if __name__ == "__main__":
    test_holidify_caching()
    print("Test passed!")
EOF
`

- [ ] **Step 2: Run test to verify it fails**

Run the test command above
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Modify the fetch_event_spike function to add caching logic:

```python
def fetch_event_spike(city: str, start_date: dt.date, end_date: dt.date) -> float:
    """
    Scrape Holidify festival page for the given city.
    If any festival date falls within [start_date, end_date], return a multiplier >1.
    Otherwise return 1.0.
    """
    # Create cache key
    cache_key = f"{city.lower()}-{start_date.isoformat()}-{end_date.isoformat()}"
    now = time.time()
    
    # Check cache first
    if cache_key in _HOLIDIFY_CACHE:
        multiplier, timestamp = _HOLIDIFY_CACHE[cache_key]
        if now - timestamp < _HOLIDIFY_CACHE_TTL:
            return multiplier

    city_slug = city.lower().replace(" ", "-")
    url = f"https://www.holidify.com/places/{city_slug}/festivals/"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        result = 1.0
        # Cache the fallback result too
        _HOLIDIFY_CACHE[cache_key] = (result, now)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")
    date_pattern = re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s*\d{4}\b",
        re.I,
    )
    date_pattern2 = re.compile(r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", re.I)

    text = soup.get_text(" ", strip=True)
    matches = date_pattern.findall(text) + date_pattern2.findall(text)
    for m in matches:
        try:
            for fmt in ("%b %d, %Y", "%d %b %Y", "%b %d %Y", "%d %b, %Y"):
                try:
                    fest_dt = dt.datetime.strptime(m.strip(), fmt).date()
                    if start_date <= fest_dt <= end_date:
                        result = 1.5
                        # Store in cache
                        _HOLIDIFY_CACHE[cache_key] = (result, now)
                        return result
                except ValueError:
                    continue
        except Exception:
            continue
    
    result = 1.0
    # Store in cache
    _HOLIDIFY_CACHE[cache_key] = (result, now)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest <(cat <<'EOF'
import time
from unittest.mock import patch
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_holidify_caching():
    city = "testcity"
    start_date = pilgrim_pulse.dt.date.today()
    end_date = start_date + pilgrim_pulse.dt.timedelta(days=2)
    
    # Clear cache
    pilgrim_pulse._HOLIDIFY_CACHE.clear()
    
    # Mock requests.get to track calls
    with patch('pilgrim_pulse.requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<html>Jan 15, 2026</html>'  # Date within range
        
        # First call
        result1 = pilgrim_pulse.fetch_event_spike(city, start_date, end_date)
        first_call_count = mock_get.call_count
        
        # Second call with same params
        result2 = pilgrim_pulse.fetch_event_spike(city, start_date, end_date)
        second_call_count = mock_get.call_count
        
        # Should only have made one HTTP request
        assert second_call_count == first_call_count == 1
        assert result1 == result2 == 1.5  # Should return event multiplier

if __name__ == "__main__":
    test_holidify_caching()
    print("Test passed!")
EOF
) -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "feat: implement caching in fetch_event_spike function"
```

### Task 5: Add cache cleanup mechanism (optional enhancement)

**Files:**
- Modify: `pilgrim_pulse.py` (add cache cleanup function and call it periodically)

- [ ] **Step 1: Write the failing test**

```python
import time
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_cache_cleanup():
    # Add some old entries
    pilgrim_pulse._AIRBNB_CACHE['old-key'] = ({'avg_price': 1000, 'occupancy': 50}, time.time() - 7*60*60)  # 7 hours old
    pilgrim_pulse._HOLIDIFY_CACHE['old-key'] = (1.5, time.time() - 7*60*60)  # 7 hours old
    
    # Add some recent entries
    pilgrim_pulse._AIRBNB_CACHE['new-key'] = ({'avg_price': 1200, 'occupancy': 60}, time.time())  # Now
    pilgrim_pulse._HOLIDIFY_CACHE['new-key'] = (1.2, time.time())  # Now
    
    initial_airbnb_size = len(pilgrim_pulse._AIRBNB_CACHE)
    initial_holidify_size = len(pilgrim_pulse._HOLIDIFY_CACHE)
    
    # Call cleanup function (we'll implement this)
    pilgrim_pulse._clean_expired_cache_entries()
    
    # Should have removed old entries
    assert len(pilgrim_pulse._AIRBNB_CACHE) < initial_airbnb_size
    assert len(pilgrim_pulse._HOLIDIFY_CACHE) < initial_holidify_size
    assert 'new-key' in pilgrim_pulse._AIRBNB_CACHE
    assert 'new-key' in pilgrim_pulse._HOLIDIFY_CACHE
    assert 'old-key' not in pilgrim_pulse._AIRBNB_CACHE
    assert 'old-key' not in pilgrim_pulse._HOLIDIFY_CACHE

if __name__ == "__main__":
    test_cache_cleanup()
    print("Test passed!")
EOF
`

- [ ] **Step 2: Run test to verify it fails**

Run the test command above
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add cache cleanup function and integrate it:

```python
def _clean_expired_cache_entries():
    """Remove expired entries from all caches to prevent memory leaks."""
    now = time.time()
    
    # Clean Airbnb cache
    expired_keys = [
        key for key, (_, timestamp) in _AIRBNB_CACHE.items()
        if now - timestamp >= _AIRBNB_CACHE_TTL
    ]
    for key in expired_keys:
        del _AIRBNB_CACHE[key]
    
    # Clean Holidify cache
    expired_keys = [
        key for key, (_, timestamp) in _HOLIDIFY_CACHE.items()
        if now - timestamp >= _HOLIDIFY_CACHE_TTL
    ]
    for key in expired_keys:
        del _HOLIDIFY_CACHE[key]
```

Then add calls to this function in both fetch functions before returning:

In fetch_airbnb_comps, before the return statement:
```python
# Clean expired cache entries periodically (every 100 calls to avoid overhead)
if len(_AIRBNB_CACHE) % 100 == 0:
    _clean_expired_cache_entries()
```

In fetch_event_spike, before the return statement:
```python
# Clean expired cache entries periodically (every 100 calls to avoid overhead)
if len(_HOLIDIFY_CACHE) % 100 == 0:
    _clean_expired_cache_entries()
```

- [ ] **Step 4: Run test to verify it passes**

Run the test command above
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "feat: add cache cleanup mechanism"
```

### Task 6: Update docstring to mention caching

**Files:**
- Modify: `pilgrim_pulse.py:12-14` (update the module docstring)

- [ ] **Step 1: Write the failing test**

```python
import sys
sys.path.insert(0, '.')
import pilgrim_pulse

def test_docstring_mentions_caching():
    docstring = pilgrim_pulse.__doc__
    assert 'cache' in docstring.lower() or 'caching' in docstring.lower()

if __name__ == "__main__":
    test_docstring_mentions_caching()
    print("Test passed!")
EOF
`

- [ ] **Step 2: Run test to verify it fails**

Run the test command above
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Update the module docstring:

```python
"""
pilgrim_pulse - CLI demand scanner for short‑term rental arbitrage in spiritual cities.

Features:
- Accepts city/area and optional date range.
- Pulls Airbnb comparable listings via HTML scraping (price strings + “X stays” count).
- Pulls pilgrimage/event data from Holidify festival pages.
- Uses Google Trends (pytrends) for accommodation interest with retry/backoff.
- Implements caching for Airbnb and Holidify requests to improve performance.
- Outputs a markdown table with a demand score and go/hold/recommendation.

Note: Scraping respects a polite user‑agent and a short delay; for production
use consider official APIs or rate‑limited scraping with caching.
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run the test command above
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pilgrim_pulse.py
git commit -m "docs: update module docstring to mention caching"
```
