document.addEventListener('DOMContentLoaded', () => {
    // Tabs
    const tabBtns = document.querySelectorAll('.tab-btn');
    const sections = document.querySelectorAll('.content-section');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
            hideNotification();
        });
    });

    // Section 1: Drag and Drop
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const btnUpload = document.getElementById('btn-upload');
    let selectedFiles = [];

    const handleFiles = (files) => {
        const validFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.png') || f.name.toLowerCase().endsWith('.zip'));
        if (validFiles.length === 0) {
            showNotification('Please select only graphic files in .png or .zip format', 'error');
            return;
        }

        selectedFiles = validFiles;
        fileList.textContent = `${selectedFiles.length} files selected.`;
        btnUpload.disabled = false;
        hideNotification();
    };

    dropZone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });

    // Section 2: Google Drive Link
    const gdriveInput = document.getElementById('gdrive-link');
    const btnGdrive = document.getElementById('btn-gdrive');

    gdriveInput.addEventListener('input', (e) => {
        btnGdrive.disabled = e.target.value.trim().length === 0;
        hideNotification();
    });

    // Notifications
    const notifBox = document.getElementById('notification-box');
    const notifMessage = document.getElementById('notif-message');

    const showNotification = (msg, type) => {
        notifBox.className = `notification ${type}`;
        notifMessage.textContent = msg;
        notifBox.classList.remove('hidden');
    };

    const hideNotification = () => {
        notifBox.classList.add('hidden');
    };

    // Helper to block UI and show loader
    const setLoading = (btn, isLoading) => {
        const textSpan = btn.querySelector('.btn-text');
        const loader = btn.querySelector('.loader');
        
        btn.disabled = isLoading;
        if (isLoading) {
            textSpan.classList.add('hidden');
            loader.classList.remove('hidden');
        } else {
            textSpan.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    };

    // Handle PDF download from blob response
    const handleDownloadBlob = (blob, defaultFilename, responseHeaders) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        let filename = defaultFilename;
        // The headers string might be available from XHR
        if (typeof responseHeaders === 'string') {
            const contentDispositionMatch = responseHeaders.match(/content-disposition:\s*.*filename=["']?([^"';]+)["']?/i);
            if (contentDispositionMatch && contentDispositionMatch[1]) {
                filename = contentDispositionMatch[1];
            }
        } else if (responseHeaders && responseHeaders.get) {
            const contentDisposition = responseHeaders.get('content-disposition');
            if (contentDisposition && contentDisposition.indexOf('filename=') !== -1) {
                filename = contentDisposition.split('filename=')[1].replace(/["']/g, '');
            }
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    };

    // Progress UI Elements
    const uploadProgressContainer = document.getElementById('upload-progress-container');
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const uploadProgressText = document.getElementById('upload-progress-text');
    
    const gdriveProgressContainer = document.getElementById('gdrive-progress-container');
    const gdriveProgressText = document.getElementById('gdrive-progress-text');

    // Actions
    btnUpload.addEventListener('click', () => {
        if (selectedFiles.length === 0) return;
        
        setLoading(btnUpload, true);
        hideNotification();
        uploadProgressContainer.classList.remove('hidden');
        uploadProgressBar.style.width = '0%';
        uploadProgressText.textContent = 'Uploading files: 0%';
        
        const formData = new FormData();
        selectedFiles.forEach(f => formData.append('files', f));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/merge/upload', true);
        xhr.responseType = 'blob'; // Oczekujemy pliku

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                uploadProgressBar.style.width = percentComplete + '%';
                if (percentComplete < 100) {
                    uploadProgressText.textContent = `Uploading files: ${percentComplete}%`;
                } else {
                    // Kiedy dojdzie do 100%, serwer jeszcze przetwarza obrazki i generuje PDF.
                    uploadProgressText.textContent = `Upload complete. Generating PDF document, please wait...`;
                }
            }
        };

        xhr.onload = () => {
            setLoading(btnUpload, false);
            uploadProgressContainer.classList.add('hidden');
            
            if (xhr.status === 200) {
                handleDownloadBlob(xhr.response, 'Ready_Cards.pdf', xhr.getAllResponseHeaders());
                showNotification('The PDF file has been successfully generated and downloaded!', 'success');
            } else {
                // Jeśli błąd, próbujemy odczytać JSON z blob
                const reader = new FileReader();
                reader.onload = () => {
                    let errorMsg = 'An unknown error occurred';
                    try {
                        const errorData = JSON.parse(reader.result);
                        errorMsg = errorData.detail || errorMsg;
                    } catch(e) {}
                    showNotification(errorMsg, 'error');
                };
                reader.readAsText(xhr.response);
            }
        };

        xhr.onerror = () => {
            setLoading(btnUpload, false);
            uploadProgressContainer.classList.add('hidden');
            showNotification('Network error occurred.', 'error');
        };

        xhr.send(formData);
    });

    btnGdrive.addEventListener('click', async () => {
        const url = gdriveInput.value.trim();
        if (!url) return;
        
        setLoading(btnGdrive, true);
        hideNotification();
        gdriveProgressContainer.classList.remove('hidden');
        gdriveProgressText.textContent = 'Downloading from Google Drive and generating PDF...';
        
        const formData = new FormData();
        formData.append('url', url);

        try {
            const response = await fetch('/api/merge/gdrive', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                let errorMsg = 'An unknown error occurred';
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.detail || errorMsg;
                } catch(e) {}
                throw new Error(errorMsg);
            }

            const blob = await response.blob();
            handleDownloadBlob(blob, 'Cards_GDrive.pdf', response.headers);
            showNotification('Successfully downloaded folder and generated PDF!', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            setLoading(btnGdrive, false);
            gdriveProgressContainer.classList.add('hidden');
        }
    });
});
