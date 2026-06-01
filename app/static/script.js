document.addEventListener('DOMContentLoaded', () => {
    // Zakładki
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

    // Sekcja 1: Przeciągnij i upuść
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const btnUpload = document.getElementById('btn-upload');
    let selectedFiles = [];

    const handleFiles = (files) => {
        const pngFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.png'));
        if (pngFiles.length === 0) {
            showNotification('Proszę wybrać tylko pliki graficzne w formacie .png', 'error');
            return;
        }

        selectedFiles = pngFiles;
        fileList.textContent = `Wybrano ${selectedFiles.length} plików.`;
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

    // Sekcja 2: Link Google Drive
    const gdriveInput = document.getElementById('gdrive-link');
    const btnGdrive = document.getElementById('btn-gdrive');

    gdriveInput.addEventListener('input', (e) => {
        btnGdrive.disabled = e.target.value.trim().length === 0;
        hideNotification();
    });

    // Powiadomienia
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

    // Helper do blokowania UI i pokazywania loadera
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

    // Obsługa pobierania PDF z odpowiedzi serwera
    const handleDownload = async (response, defaultFilename) => {
        if (!response.ok) {
            let errorMsg = 'Wystąpił nieznany błąd';
            try {
                const errorData = await response.json();
                errorMsg = errorData.detail || errorMsg;
            } catch(e) {}
            throw new Error(errorMsg);
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        
        // Próba odczytania nazwy pliku z nagłówków
        let filename = defaultFilename;
        const contentDisposition = response.headers.get('content-disposition');
        if (contentDisposition && contentDisposition.indexOf('filename=') !== -1) {
            filename = contentDisposition.split('filename=')[1].replace(/["']/g, '');
        }

        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    };

    // Akcje
    btnUpload.addEventListener('click', async () => {
        if (selectedFiles.length === 0) return;
        
        setLoading(btnUpload, true);
        hideNotification();
        
        const formData = new FormData();
        selectedFiles.forEach(f => formData.append('files', f));

        try {
            const response = await fetch('/api/merge/upload', {
                method: 'POST',
                body: formData
            });
            await handleDownload(response, 'Gotowe_Karty.pdf');
            showNotification('Plik PDF został pomyślnie wygenerowany i pobrany!', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            setLoading(btnUpload, false);
        }
    });

    btnGdrive.addEventListener('click', async () => {
        const url = gdriveInput.value.trim();
        if (!url) return;
        
        setLoading(btnGdrive, true);
        hideNotification();
        
        const formData = new FormData();
        formData.append('url', url);

        try {
            const response = await fetch('/api/merge/gdrive', {
                method: 'POST',
                body: formData
            });
            await handleDownload(response, 'Karty_GDrive.pdf');
            showNotification('Udało się pobrać folder i wygenerować plik PDF!', 'success');
        } catch (error) {
            showNotification(error.message, 'error');
        } finally {
            setLoading(btnGdrive, false);
        }
    });
});
