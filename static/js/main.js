document.addEventListener('DOMContentLoaded', function() {
    // Flash message auto-dismiss
    const flashMessages = document.querySelectorAll('.alert-dismissible');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            const closeButton = message.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        }, 5000); // Auto dismiss after 5 seconds
    });

    // Form validation for signup
    const signupForm = document.getElementById('signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function(event) {
            let valid = true;
            
            // Name validation
            const nameInput = document.getElementById('name');
            if (nameInput.value.trim() === '') {
                showError(nameInput, 'Name is required');
                valid = false;
            } else {
                clearError(nameInput);
            }
            
            // Email validation
            const emailInput = document.getElementById('email');
            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailPattern.test(emailInput.value.trim())) {
                showError(emailInput, 'Enter a valid email address');
                valid = false;
            } else {
                clearError(emailInput);
            }
            
            // Password validation
            const passwordInput = document.getElementById('password');
            if (passwordInput.value.length < 6) {
                showError(passwordInput, 'Password must be at least 6 characters');
                valid = false;
            } else {
                clearError(passwordInput);
            }
            
            if (!valid) {
                event.preventDefault();
            }
        });
    }
    
    // Form validation for login
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function(event) {
            let valid = true;
            
            // Email validation
            const emailInput = document.getElementById('login-email');
            if (emailInput.value.trim() === '') {
                showError(emailInput, 'Email is required');
                valid = false;
            } else {
                clearError(emailInput);
            }
            
            // Password validation
            const passwordInput = document.getElementById('login-password');
            if (passwordInput.value.trim() === '') {
                showError(passwordInput, 'Password is required');
                valid = false;
            } else {
                clearError(passwordInput);
            }
            
            if (!valid) {
                event.preventDefault();
            }
        });
    }
    
    // Report upload form
    const reportForm = document.getElementById('report-form');
    if (reportForm) {
        reportForm.addEventListener('submit', function(event) {
            const fileInput = document.getElementById('report');
            if (fileInput.files.length === 0) {
                event.preventDefault();
                showUploadError('Please select a file to upload');
                return;
            }
            
            const fileName = fileInput.files[0].name;
            const fileExtension = fileName.split('.').pop().toLowerCase();
            
            // Only allow certain file types
            const allowedExtensions = ['pdf', 'doc', 'docx', 'txt', 'rtf'];
            if (!allowedExtensions.includes(fileExtension)) {
                event.preventDefault();
                showUploadError('Invalid file type. Please upload a PDF, DOC, DOCX, TXT, or RTF file.');
                return;
            }
            
            // Show loading spinner
            document.getElementById('spinner').style.display = 'block';
            document.getElementById('upload-btn').disabled = true;
        });
    }
    
    // Drag and drop functionality for file upload
    const uploadZone = document.getElementById('upload-zone');
    if (uploadZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            uploadZone.classList.add('dragover');
        }
        
        function unhighlight() {
            uploadZone.classList.remove('dragover');
        }
        
        uploadZone.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            document.getElementById('report').files = files;
            
            // Update file name display
            if (files.length > 0) {
                document.getElementById('file-name').textContent = files[0].name;
            }
        }
        
        // Click to upload
        uploadZone.addEventListener('click', function() {
            document.getElementById('report').click();
        });
        
        // Display selected file name
        document.getElementById('report').addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                document.getElementById('file-name').textContent = e.target.files[0].name;
            } else {
                document.getElementById('file-name').textContent = 'No file selected';
            }
        });
    }
    
    // Helper functions for validation
    function showError(input, message) {
        const formControl = input.parentElement;
        const errorElement = formControl.querySelector('.invalid-feedback') || document.createElement('div');
        errorElement.className = 'invalid-feedback';
        errorElement.textContent = message;
        
        if (!formControl.querySelector('.invalid-feedback')) {
            formControl.appendChild(errorElement);
        }
        
        input.classList.add('is-invalid');
    }
    
    function clearError(input) {
        input.classList.remove('is-invalid');
    }
    
    function showUploadError(message) {
        const errorDiv = document.getElementById('upload-error');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
});
