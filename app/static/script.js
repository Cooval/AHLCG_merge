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
    const btnClearUpload = document.getElementById('btn-clear-upload');
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
        btnClearUpload.classList.remove('hidden');
        hideNotification();
    };

    const clearUploadState = () => {
        selectedFiles = [];
        fileInput.value = '';
        fileList.textContent = '';
        btnUpload.disabled = true;
        btnClearUpload.classList.add('hidden');
        uploadProgressContainer.classList.add('hidden');
        uploadConsole.textContent = '';
    };

    btnClearUpload.addEventListener('click', clearUploadState);

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

    // handleDownloadBlob deleted in favor of native browser downloading

    // Progress UI Elements
    const uploadProgressContainer = document.getElementById('upload-progress-container');
    const uploadProgressBar = document.getElementById('upload-progress-bar');
    const uploadProgressText = document.getElementById('upload-progress-text');
    
    const gdriveProgressContainer = document.getElementById('gdrive-progress-container');
    const gdriveProgressText = document.getElementById('gdrive-progress-text');

    const uploadConsole = document.getElementById('upload-console');
    const gdriveConsole = document.getElementById('gdrive-console');

    const appendLog = (consoleEl, text) => {
        consoleEl.textContent += text + '\n';
        consoleEl.scrollTop = consoleEl.scrollHeight;
    };

    const startSSE = (jobId, consoleEl, btn, progressContainer, defaultFilename) => {
        consoleEl.classList.add('active');
        consoleEl.textContent = "Waiting for server logs...\n";
        
        const eventSource = new EventSource('/api/merge/process/' + jobId);
        
        eventSource.onmessage = (e) => {
            const data = e.data;
            if (data === "DONE") {
                eventSource.close();
                appendLog(consoleEl, "Processing complete! Downloading PDF...");
                
                try {
                    const a = document.createElement('a');
                    a.href = '/api/merge/download/' + jobId;
                    a.download = defaultFilename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    
                    showNotification('The PDF file has been generated and download has started!', 'success');
                    
                    if (btn === btnUpload) {
                        clearUploadState();
                    }
                } catch(err) {
                    showNotification("Failed to start download.", 'error');
                } finally {
                    setLoading(btn, false);
                    progressContainer.classList.add('hidden');
                    consoleEl.classList.remove('active');
                }
            } else if (data.startsWith("ERROR:")) {
                eventSource.close();
                appendLog(consoleEl, data);
                showNotification(data.replace("ERROR: ", ""), 'error');
                setLoading(btn, false);
                progressContainer.classList.add('hidden');
            } else {
                appendLog(consoleEl, data);
            }
        };
        
        eventSource.onerror = () => {
            eventSource.close();
            appendLog(consoleEl, "Connection to server lost.");
            showNotification("Lost connection during processing.", 'error');
            setLoading(btn, false);
            progressContainer.classList.add('hidden');
        };
    };

    const modal = document.getElementById('resolution-modal');
    const btnCancelModal = document.getElementById('btn-cancel-modal');
    const btnConfirmResolution = document.getElementById('btn-confirm-resolution');
    
    const globalBackSection = document.getElementById('global-back-section');
    const candidatesGrid = document.getElementById('candidates-grid');
    const conflictsSection = document.getElementById('conflicts-section');
    const conflictsList = document.getElementById('conflicts-list');
    
    let currentJobId = null;
    let selectedCandidate = null;
    let currentConsoleEl = null;
    let currentBtn = null;
    let currentProgressContainer = null;
    let currentDefaultFilename = null;

    const closeAndResetModal = () => {
        modal.classList.add('hidden');
        candidatesGrid.innerHTML = '';
        conflictsList.innerHTML = '';
        globalBackSection.classList.add('hidden');
        conflictsSection.classList.add('hidden');
        
        currentJobId = null;
        selectedCandidate = null;
        btnConfirmResolution.disabled = true;
        
        if (currentBtn) setLoading(currentBtn, false);
        if (currentProgressContainer) currentProgressContainer.classList.add('hidden');
    };

    btnCancelModal.addEventListener('click', closeAndResetModal);

    btnConfirmResolution.addEventListener('click', async () => {
        if (!currentJobId) return;
        
        btnConfirmResolution.disabled = true;
        
        const payload = {
            selected_back: selectedCandidate,
            alt_keeps: [],
            old_keeps: [],
            unmatched_keeps: []
        };
        
        // Zbieranie konfliktów
        document.querySelectorAll('input[type="checkbox"][data-type="alt_conflict"]:checked').forEach(cb => {
            payload.alt_keeps.push(cb.value);
        });
        document.querySelectorAll('input[type="checkbox"][data-type="skipped_old"]:checked').forEach(cb => {
            payload.old_keeps.push(cb.value);
        });
        document.querySelectorAll('input[type="checkbox"][data-type="skipped_unmatched"]:checked').forEach(cb => {
            payload.unmatched_keeps.push(cb.value);
        });
        
        try {
            const response = await fetch('/api/merge/resolve_conflicts/' + currentJobId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) throw new Error("Failed to resolve conflicts");
            
            modal.classList.add('hidden');
            btnConfirmResolution.disabled = false;
            startSSE(currentJobId, currentConsoleEl, currentBtn, currentProgressContainer, currentDefaultFilename);
        } catch (e) {
            showNotification('Error during conflict resolution.', 'error');
            closeAndResetModal();
            btnConfirmResolution.disabled = false;
        }
    });

    const handleProcessStart = (data, consoleEl, btn, progressContainer, defaultFilename) => {
        if (data.status === 'needs_resolution') {
            currentJobId = data.job_id;
            currentConsoleEl = consoleEl;
            currentBtn = btn;
            currentProgressContainer = progressContainer;
            currentDefaultFilename = defaultFilename;
            
            candidatesGrid.innerHTML = '';
            conflictsList.innerHTML = '';
            globalBackSection.classList.add('hidden');
            conflictsSection.classList.add('hidden');
            selectedCandidate = null;
            
            // 1. Global Back Selection
            if (data.needs_back) {
                btnConfirmResolution.disabled = true;
                
                if (!data.back_candidates || data.back_candidates.length === 0) {
                    showNotification("No back candidates found, and some cards lack a back. Process aborted.", "error");
                    setLoading(btn, false);
                    progressContainer.classList.add('hidden');
                    return;
                }
                
                globalBackSection.classList.remove('hidden');
                
                data.back_candidates.forEach(filename => {
                    const item = document.createElement('div');
                    item.className = 'candidate-item';
                    
                    const img = document.createElement('img');
                    img.src = `/api/merge/preview/${data.job_id}/${filename}`;
                    img.alt = filename;
                    
                    const label = document.createElement('div');
                    label.className = 'candidate-name';
                    label.textContent = filename;
                    
                    item.appendChild(img);
                    item.appendChild(label);
                    
                    item.addEventListener('click', () => {
                        document.querySelectorAll('.candidate-item').forEach(el => el.classList.remove('selected'));
                        item.classList.add('selected');
                        selectedCandidate = filename;
                        btnConfirmResolution.disabled = false;
                    });
                    
                    candidatesGrid.appendChild(item);
                });
            } else {
                btnConfirmResolution.disabled = false;
            }
            
            // 2. Conflicts
            if (data.conflicts && data.conflicts.length > 0) {
                conflictsSection.classList.remove('hidden');
                
                data.conflicts.forEach(conflict => {
                    const cItem = document.createElement('div');
                    cItem.className = 'conflict-item';
                    
                    const header = document.createElement('div');
                    header.className = 'conflict-header';
                    header.textContent = conflict.description;
                    cItem.appendChild(header);
                    
                    const optionsDiv = document.createElement('div');
                    optionsDiv.className = 'conflict-options';
                    
                    conflict.options.forEach(opt => {
                        const optDiv = document.createElement('label');
                        optDiv.className = 'conflict-option';
                        
                        const img = document.createElement('img');
                        img.src = `/api/merge/preview/${data.job_id}/${opt.filename}`;
                        
                        const cb = document.createElement('input');
                        cb.type = 'checkbox';
                        cb.dataset.type = conflict.type;
                        cb.value = opt.base_name || opt.filename;
                        
                        // Zaznacz mylnie jako checked by domyślnie sugerować "weź" (albo zostawmy puste dla alt)
                        if (conflict.type !== 'alt_conflict') {
                            // old i unmatched - domyślnie odznaczone
                        } else {
                            // alt_conflict domyślnie odznaczone
                        }
                        
                        const textSpan = document.createElement('span');
                        textSpan.textContent = opt.label;
                        
                        cb.addEventListener('change', () => {
                            if (cb.checked) {
                                optDiv.classList.add('selected');
                            } else {
                                optDiv.classList.remove('selected');
                            }
                        });
                        
                        optDiv.appendChild(img);
                        optDiv.appendChild(cb);
                        optDiv.appendChild(textSpan);
                        
                        optionsDiv.appendChild(optDiv);
                    });
                    
                    cItem.appendChild(optionsDiv);
                    conflictsList.appendChild(cItem);
                });
            }
            
            modal.classList.remove('hidden');
        } else if (data.status === 'ready') {
            startSSE(data.job_id, consoleEl, btn, progressContainer, defaultFilename);
        }
    };

    // Actions
    btnUpload.addEventListener('click', () => {
        if (selectedFiles.length === 0) return;
        
        setLoading(btnUpload, true);
        hideNotification();
        uploadProgressContainer.classList.remove('hidden');
        uploadProgressBar.style.width = '0%';
        uploadProgressText.textContent = 'Uploading files: 0%';
        uploadConsole.classList.remove('active');
        uploadConsole.textContent = '';
        
        const formData = new FormData();
        selectedFiles.forEach(f => formData.append('files', f));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/merge/upload', true);
        xhr.responseType = 'json';

        xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                uploadProgressBar.style.width = percentComplete + '%';
                if (percentComplete < 100) {
                    uploadProgressText.textContent = `Uploading files: ${percentComplete}%`;
                } else {
                    uploadProgressText.textContent = `Upload complete. Starting backend processor...`;
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status === 200 && xhr.response.job_id) {
                uploadProgressText.textContent = `Server processing...`;
                handleProcessStart(xhr.response, uploadConsole, btnUpload, uploadProgressContainer, 'Ready_Cards.pdf');
            } else {
                let errorMsg = 'An unknown error occurred';
                if (xhr.response && xhr.response.detail) {
                    errorMsg = xhr.response.detail;
                }
                showNotification(errorMsg, 'error');
                setLoading(btnUpload, false);
                uploadProgressContainer.classList.add('hidden');
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
        gdriveProgressText.textContent = 'Downloading from Google Drive and analyzing...';
        gdriveConsole.classList.remove('active');
        gdriveConsole.textContent = '';
        
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

            const data = await response.json();
            if (data.job_id) {
                gdriveProgressText.textContent = 'Server processing...';
                handleProcessStart(data, gdriveConsole, btnGdrive, gdriveProgressContainer, 'Cards_GDrive.pdf');
            }
        } catch (error) {
            showNotification(error.message, 'error');
            setLoading(btnGdrive, false);
            gdriveProgressContainer.classList.add('hidden');
        }
    });
});
