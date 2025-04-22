document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize all popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Card animations for dashboard
    animateCards();
    
    // Counter animations
    animateCounters();
    
    // Form animations
    animateForms();
    
    // Add loading state to buttons on submit
    setupFormLoadingState();
    
    // Setup password toggles
    setupPasswordToggle();
    
    // Setup search functionality
    setupSearch();
});

// Animate cards with staggered delay
function animateCards() {
    const cards = document.querySelectorAll('.card');
    
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(20px)';
            
            setTimeout(() => {
                card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            }, 50);
        }, 100 * index);
    });
}

// Animate counters
function animateCounters() {
    const counters = document.querySelectorAll('.counter-value');
    
    counters.forEach((counter, index) => {
        setTimeout(() => {
            counter.classList.add('animated');
            
            // If it's a number, do a counting animation
            const targetValue = counter.textContent;
            if (!isNaN(targetValue) && targetValue.trim() !== '') {
                const target = parseInt(targetValue);
                if (target <= 100) { // Only animate if it's a reasonable number
                    counter.textContent = '0';
                    let current = 0;
                    const increment = target / 20;
                    const interval = setInterval(() => {
                        current += increment;
                        counter.textContent = Math.round(current);
                        if (current >= target) {
                            counter.textContent = target;
                            clearInterval(interval);
                        }
                    }, 50);
                }
            }
        }, 200 * index);
    });
}

// Animate form elements
function animateForms() {
    const formElements = document.querySelectorAll('.form-control, .form-select, .form-check, .btn-submit');
    
    formElements.forEach((element, index) => {
        setTimeout(() => {
            element.classList.add('fadeInDown');
        }, 100 * index);
    });
}

// Add loading state to buttons on submit
function setupFormLoadingState() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.classList.add('btn-loading');
                submitBtn.disabled = true;
                
                // Find or create spinner
                let spinner = submitBtn.querySelector('.spinner-border');
                if (!spinner) {
                    // Create and add spinner
                    spinner = document.createElement('span');
                    spinner.className = 'spinner-border spinner-border-sm';
                    spinner.setAttribute('role', 'status');
                    spinner.setAttribute('aria-hidden', 'true');
                    submitBtn.appendChild(spinner);
                }
                
                // Wrap text in span if not already
                const btnText = submitBtn.textContent.trim();
                if (!submitBtn.querySelector('.btn-text')) {
                    submitBtn.innerHTML = '';
                    const textSpan = document.createElement('span');
                    textSpan.className = 'btn-text';
                    textSpan.textContent = btnText;
                    submitBtn.appendChild(textSpan);
                    submitBtn.appendChild(spinner);
                }
            }
        });
    });
}

// Setup password visibility toggle
function setupPasswordToggle() {
    const toggleButtons = document.querySelectorAll('.toggle-password');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            
            // Change icon
            const icon = this.querySelector('i');
            if (icon) {
                if (type === 'password') {
                    icon.className = 'fas fa-eye';
                } else {
                    icon.className = 'fas fa-eye-slash';
                }
            }
        });
    });
}

// Setup search functionality
function setupSearch() {
    const searchInputs = document.querySelectorAll('input[id$="Search"]');
    
    searchInputs.forEach(input => {
        input.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const tableId = this.id.replace('Search', 'Table');
            const table = document.getElementById(tableId);
            
            if (table) {
                const rows = table.querySelectorAll('tbody tr');
                
                rows.forEach(row => {
                    const text = row.textContent.toLowerCase();
                    if (text.includes(searchTerm)) {
                        row.style.display = '';
                    } else {
                        row.style.display = 'none';
                    }
                });
            }
        });
    });
}

// Function to show a confirmation dialog
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Function to format dates nicely
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Function to check password strength
function checkPasswordStrength(password) {
    let strength = 0;
    
    // Length check
    if (password.length >= 8) strength += 25;
    
    // Contains uppercase
    if (password.match(/[A-Z]/)) strength += 25;
    
    // Contains number
    if (password.match(/[0-9]/)) strength += 25;
    
    // Contains special character
    if (password.match(/[^A-Za-z0-9]/)) strength += 25;
    
    return strength;
}

// Function to update password strength meter
function updatePasswordStrength(password, progressBar, strengthText) {
    const strength = checkPasswordStrength(password);
    
    progressBar.style.width = strength + '%';
    
    if (strength <= 25) {
        progressBar.className = 'progress-bar bg-danger';
        strengthText.textContent = 'Weak password';
    } else if (strength <= 50) {
        progressBar.className = 'progress-bar bg-warning';
        strengthText.textContent = 'Fair password';
    } else if (strength <= 75) {
        progressBar.className = 'progress-bar bg-info';
        strengthText.textContent = 'Good password';
    } else {
        progressBar.className = 'progress-bar bg-success';
        strengthText.textContent = 'Strong password';
    }
}