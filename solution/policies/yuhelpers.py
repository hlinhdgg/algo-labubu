class Queue:
    """A linear Queue ADT (First-In, First-Out) implemented using a Python list."""
    def __init__(self):
        self._items = []

    def is_empty(self):
        return len(self._items) == 0

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        if not self.is_empty():
            return self._items.pop(0)  # O(n) list shift, or use collections.deque for O(1)
        return None

    def peek(self):
        if not self.is_empty():
            return self._items[0]
        return None

    def size(self):
        return len(self._items)


def merge_sort_parcels(parcels_list, key_func):
    """
    Recursive Merge Sort algorithm to sort parcels based on a key function 
    (e.g., delivery_window_end).
    Complexity: O(n log n) time, O(n) space.
    """
    # 1. Base case: lists with 0 or 1 element are already sorted
    if len(parcels_list) <= 1:
        return parcels_list

    # 2. Divide step
    mid = len(parcels_list) // 2
    left_half = merge_sort_parcels(parcels_list[:mid], key_func)
    right_half = merge_sort_parcels(parcels_list[mid:], key_func)

    # 3. Conquer / Merge step
    return _merge(left_half, right_half, key_func)


def _merge(left, right, key_func):
    sorted_result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if key_func(left[i]) <= key_func(right[j]):
            sorted_result.append(left[i])
            i += 1
        else:
            sorted_result.append(right[j])
            j += 1

    # Append any remaining elements
    sorted_result.extend(left[i:])
    sorted_result.extend(right[j:])
    return sorted_result

def binary_search_first_active_index(sorted_parcels, current_time):
    """
    Uses Binary Search to find the index of the first parcel whose 
    delivery_window_end is greater than or equal to current_time.
    Complexity: O(log n) time.
    """
    low = 0
    high = len(sorted_parcels) - 1
    result_index = len(sorted_parcels)  # Default if none match

    while low <= high:
        mid = (low + high) // 2
        # Check delivery_window_end of the parcel at mid
        window_end = float(sorted_parcels[mid][1]["delivery_window_end"])

        if window_end >= current_time:
            result_index = mid  # Found a candidate, try to find an even earlier valid one on the left
            high = mid - 1
        else:
            low = mid + 1

    return result_index
