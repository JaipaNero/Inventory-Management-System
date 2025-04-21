// Custom JavaScript for the Inventory Management System

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all Materialize components
    M.AutoInit();
    
    // Initialize tooltips
    var elems = document.querySelectorAll('.tooltipped');
    var instances = M.Tooltip.init(elems);
    
    // Initialize modals
    var modalElems = document.querySelectorAll('.modal');
    var modalInstances = M.Modal.init(modalElems);
    
    // Initialize dropdown menus
    var dropdownElems = document.querySelectorAll('.dropdown-trigger');
    var dropdownInstances = M.Dropdown.init(dropdownElems, {
        coverTrigger: false,
        constrainWidth: false
    });

    // Store selector functionality
    const storeSelector = document.getElementById('store-selector');
    if (storeSelector) {
        storeSelector.addEventListener('change', function() {
            const storeId = this.value;
            if (storeId) {
                // Show loading indicator
                document.getElementById('store-loading').style.display = 'inline-block';
                
                // Send AJAX request to change active store
                fetch('/set_active_store', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrf_token')
                    },
                    body: JSON.stringify({ store_id: storeId }),
                    credentials: 'same-origin'
                })
                .then(response => {
                    if (response.ok) {
                        // Reload page to reflect the new store context
                        window.location.reload();
                    } else {
                        throw new Error('Failed to set active store');
                    }
                })
                .catch(error => {
                    M.toast({html: 'Error changing store: ' + error.message, classes: 'red'});
                    document.getElementById('store-loading').style.display = 'none';
                });
            }
        });
    }

    // Accessory/Clothing type switch functionality
    const typeSwitch = document.getElementById('type-switch');
    if (typeSwitch) {
        typeSwitch.addEventListener('change', function() {
            const isClothingSelected = this.checked;
            const inventoryType = isClothingSelected ? 'clothing' : 'accessories';
            
            // Show loading indicator
            document.getElementById('type-loading').style.display = 'inline-block';
            
            // Redirect to the appropriate inventory list
            window.location.href = '/inventory/' + inventoryType;
        });
    }

    // Dynamic filtering for inventory tables
    const inventorySearch = document.getElementById('inventory-search');
    if (inventorySearch) {
        inventorySearch.addEventListener('keyup', function() {
            const searchValue = this.value.toLowerCase();
            const tableRows = document.querySelectorAll('#inventory-table tbody tr');
            
            tableRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(searchValue)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });
        });
    }

    // Dynamic accessory selection in register outgoing form
    const accessorySelect = document.getElementById('accessory-select');
    if (accessorySelect) {
        accessorySelect.addEventListener('change', function() {
            const selectedOption = this.options[this.selectedIndex];
            const partNumber = selectedOption.getAttribute('data-part-number');
            const partDescription = selectedOption.getAttribute('data-description');
            
            // Update the part details section
            const partDetails = document.getElementById('part-details');
            if (partDetails) {
                partDetails.innerHTML = `
                    <p><strong>Part Number:</strong> ${partNumber || 'N/A'}</p>
                    <p><strong>Description:</strong> ${partDescription || 'N/A'}</p>
                `;
            }
        });
        
        // Trigger initial change to populate part details
        if (accessorySelect.value) {
            accessorySelect.dispatchEvent(new Event('change'));
        }
    }

    // Helper function to get CSRF token from cookies
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }
});

// Add this function to your script.js
function showPreloader(targetElement) {
    const preloaderHtml = `
        <div class="center-align" style="padding: 20px;">
            <div class="preloader-wrapper active">
                <div class="spinner-layer spinner-teal-only">
                    <div class="circle-clipper left">
                        <div class="circle"></div>
                    </div>
                    <div class="gap-patch">
                        <div class="circle"></div>
                    </div>
                    <div class="circle-clipper right">
                        <div class="circle"></div>
                    </div>
                </div>
            </div>
            <p>Loading data...</p>
        </div>
    `;
    
    document.querySelector(targetElement).innerHTML = preloaderHtml;
}