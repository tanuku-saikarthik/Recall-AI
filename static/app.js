document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const searchContainer = document.getElementById('search-container');
    const resultsContainer = document.getElementById('results-container');
    const statusMsg = document.getElementById('search-status');
    
    // Modal elements
    const settingsBtn = document.getElementById('open-settings');
    const closeSettingsBtn = document.getElementById('close-settings');
    const overlay = document.getElementById('settings-overlay');
    const addFolderBtn = document.getElementById('add-folder-btn');
    const newFolderInput = document.getElementById('new-folder-path');
    const folderList = document.getElementById('folder-list');
    const scanBtn = document.getElementById('run-scan-btn');

    // Search Logic
    const performSearch = async () => {
        const query = searchInput.value.trim();
        if (!query) return;

        // Animate search bar to top
        searchContainer.classList.remove('center-state');
        resultsContainer.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        statusMsg.textContent = 'Searching...';

        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            if (!res.ok) throw new Error('Search failed');
            const data = await res.json();
            
            statusMsg.textContent = `Found ${data.length} result(s)`;
            
            if (data.length === 0) {
                resultsContainer.innerHTML = '<div style="color:var(--text-secondary); text-align:center; grid-column:1/-1;">No results found.</div>';
                return;
            }

            data.forEach((item, index) => {
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.animationDelay = `${index * 0.1}s`;

                // Highlight matching words (naive implementation)
                const terms = query.split(' ').filter(t => t.length > 2);
                let highlightedPreview = item.preview;
                terms.forEach(term => {
                    const regex = new RegExp(`(${term})`, 'gi');
                    highlightedPreview = highlightedPreview.replace(regex, '<span style="color: var(--accent-color); font-weight: bold;">$1</span>');
                });

                card.innerHTML = `
                    <div class="result-header">
                        <div class="result-title">${item.file_path.split('\\').pop().split('/').pop()}</div>
                        <div class="result-score">Score: ${item.score.toFixed(3)}</div>
                    </div>
                    <div class="result-path" title="${item.file_path}">${item.file_path} ${item.page ? `(Page ${item.page})` : ''}</div>
                    <div class="result-preview">${highlightedPreview}</div>
                `;
                resultsContainer.appendChild(card);
            });

        } catch (err) {
            statusMsg.textContent = 'Error executing search.';
            console.error(err);
        }
    };

    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    // Settings Logic
    const loadFolders = async () => {
        try {
            const res = await fetch('/api/folders');
            const data = await res.json();
            folderList.innerHTML = '';
            data.forEach(f => {
                const li = document.createElement('li');
                li.innerHTML = `<span>${f.path}</span>`;
                folderList.appendChild(li);
            });
        } catch (err) {
            console.error(err);
        }
    };

    settingsBtn.addEventListener('click', () => {
        overlay.classList.remove('hidden');
        loadFolders();
    });

    closeSettingsBtn.addEventListener('click', () => {
        overlay.classList.add('hidden');
    });

    addFolderBtn.addEventListener('click', async () => {
        const path = newFolderInput.value.trim();
        if (!path) return;

        addFolderBtn.textContent = 'Adding...';
        try {
            const res = await fetch('/api/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            if (res.ok) {
                newFolderInput.value = '';
                await loadFolders();
            } else {
                alert('Failed to add folder. Does it exist?');
            }
        } catch (err) {
            console.error(err);
        } finally {
            addFolderBtn.textContent = 'Add Folder';
        }
    });

    scanBtn.addEventListener('click', async () => {
        scanBtn.textContent = 'Starting...';
        try {
            await fetch('/api/scan', { method: 'POST' });
            alert('Background scan started! It may take a few moments.');
        } catch (err) {
            console.error(err);
        } finally {
            scanBtn.textContent = 'Run Background Scan';
        }
    });
});
