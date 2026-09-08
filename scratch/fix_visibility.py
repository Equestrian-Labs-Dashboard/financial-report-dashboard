import re

with open('docs/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_vis = r'''      function syncFilterVisibility() {
        const isCavali = brandFilter.value === "Cavali";
        const locationGroup = locationFilter.closest(".filter-group");

        quarterFilterGroup.style.display = isCavali ? "flex" : "none";
        if (!isCavali) quarterFilter.value = "all";

        // Wellington and Concierge are Corro-only. Hide Split when Cavali is selected.
        if (locationGroup) locationGroup.style.display = isCavali ? "none" : "flex";
        if (isCavali) locationFilter.value = "all";
      }'''

new_vis = r'''      function syncFilterVisibility() {
        const isCavali = brandFilter.value === "Cavali";
        const locationGroup = locationFilter.closest(".filter-group");

        quarterFilterGroup.style.display = "flex"; // Always show quarter filter

        // Wellington and Concierge are Corro-only. Hide Split when Cavali is selected.
        if (locationGroup) locationGroup.style.display = isCavali ? "none" : "flex";
        if (isCavali) locationFilter.value = "all";
      }'''

content = content.replace(old_vis, new_vis)

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(content)
