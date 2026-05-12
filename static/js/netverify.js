/**
 * netverify.snapshots.js
 *
 * This script manages the snapshot listing, creation, and viewing functionality
 * for the NetVerify blueprint. It uses jQuery and DataTables for dynamic UI
 * interactions and fetch API for server communication.
 *
 * Key Features:
 * - Displays a list of snapshots with details and actions.
 * - Allows users to create new snapshots via a modal form.
 * - Provides a detailed view of snapshot outputs organized by device and command.
 * - Handles snapshot deletion with confirmation.
 */

let createSnapshotCallback = null;

$(document).ready(() => {
    /**
     * --------------------------------------------------------------------------
     * Constants & Cached DOM Elements
     * --------------------------------------------------------------------------
     */

    const API_ENDPOINTS = {
        connectors: '/api/connectors',
        snapshots: '/netverify/api/snapshots',
        snapshotFile: filename => `/netverify/api/snapshot/${filename}`,
        downloadSnapshot: filename => `/netverify/api/snapshot/download/${filename}`,
        reports: '/netverify/api/reports',
        reportFile: filename => `/netverify/api/report/${filename}`,
        downloadReport: filename => `/netverify/api/report/download/${filename}`
    };

    const UI_TEXT = {
        createLoading: `
            <span class="material-icons spin">autorenew</span>
            Creating...
        `,
        createDefault: `
            <span class="material-icons">add_a_photo</span>
            Create
        `
    };

    const validateBtn = document.getElementById('validateSnapshotsBtn');
    const createSnapshotBtn = document.getElementById('createSnapshotBtn');
    const createSnapshotModal = document.getElementById('createSnapshotModal');
    const createSnapshotForm = document.getElementById('createSnapshotForm');
    const connectorSelect = document.getElementById('snapshotConnector');

    const $snapshotsTable = $('#snapshotsTable');
    const $viewSnapshotModal = $('#viewSnapshotModal');
    const $snapshotDeviceTabs = $('#snapshotDeviceTabs');
    const $snapshotCommandTabs = $('#snapshotCommandTabs');
    const $snapshotOutput = $('#snapshotOutput');
    const $viewSnapshotTitle = $('#viewSnapshotTitle');

    /**
     * --------------------------------------------------------------------------
     * Application State
     * --------------------------------------------------------------------------
     */

    let currentSnapshot = null;
    let currentDevice = null;
    let currentCommand = null;

    /**
     * --------------------------------------------------------------------------
     * Utilities
     * --------------------------------------------------------------------------
     */

    /**
     * Displays a user-friendly error message.
     *
     * @param {string} message
     * @param {Error} [error]
     */
    const handleError = (message, error = null) => {
        console.error(message, error);
        alert(message);
    };

    /**
     * Performs a fetch request and parses JSON response.
     *
     * @param {string} url
     * @param {Object} options
     * @returns {Promise<Object>}
     */
    const fetchJson = async (url, options = {}) => {
        const response = await fetch(url, options);

        if (!response.ok) {
            throw new Error(`Request failed with status ${response.status}`);
        }

        return response.json();
    };

    /**
     * Toggles visibility of the validate snapshots button
     * based on selected rows.
     */
    const updateValidateButtonVisibility = () => {
        const selectedRows = $('.row-check:checked')
            .map(function () {
                return {
                    type: $(this).data('type')
                };
            })
            .get();

        if (selectedRows.length !== 2) {
            validateBtn.style.display = 'none';
            return;
        }

        const types = selectedRows.map(row => row.type);

        const hasPre = types.includes('pre');
        const hasPost = types.includes('post');

        validateBtn.style.display =
            hasPre && hasPost ? 'flex' : 'none';
    };

    /**
     * Resets and closes the create snapshot modal.
     */
    const closeModal = () => {
        createSnapshotModal.style.display = 'none';
        createSnapshotForm.reset();
    };

    /**
     * --------------------------------------------------------------------------
     * DataTable Initialization
     * --------------------------------------------------------------------------
     */

    const table = $snapshotsTable.DataTable({
        orderCellsTop: true,
        fixedHeader: true,
        ajax: {
            url: API_ENDPOINTS.snapshots,
            dataSrc: 'data'
        },

        columns: [
            {
                data: null,
                render: data => `
                    <input
                        type="checkbox"
                        class="row-check"
                        data-id="${data.filename}"
                        data-type="${data.type}">
                `
            },
            { data: 'filename' },
            { data: 'name' },
            {
                data: 'type',
                render: type => `
                    <span class="snapshot-type ${type}">
                        ${type?.toUpperCase() || '-'}
                    </span>
                `
            },
            {
                data: 'devices',
                render: devices => devices.join('<br>')
            },

            { data: 'creator' },
            { data: 'timestamp' },

            {
                data: null,
                render: data => `
                    <div class="actions">
                        <button class="view-snapshot-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">open_in_new</span>
                            View
                        </button>
                        <button class="delete-snapshot-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">delete</span>
                            Delete
                        </button>
                        <button class="download-snapshot-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">download</span>
                            Download
                        </button>
                    </div>
                `
            }
        ],
        columnDefs: [
            {
                width: '30px',
                targets: 0
            }
        ],
        initComplete: function () {
            const api = this.api();

            api.columns().every(function (index) {

                // Skip checkbox and actions columns
                if (index === 0 || index === 7) {
                    return;
                }

                const column = this;

                $('input', $('.filters th').eq(index))
                    .on('keyup change clear', function () {

                        if (column.search() !== this.value) {
                            column.search(this.value).draw();
                        }
                    });
            });
        }
    });

    /**
     * --------------------------------------------------------------------------
     * Connector Loading
     * --------------------------------------------------------------------------
     */

    /**
     * Loads available connectors into the connector dropdown.
     */
    const loadConnectors = async () => {
        connectorSelect.innerHTML = `
            <option value="">-- Select Connector --</option>
        `;

        try {
            const data = await fetchJson(API_ENDPOINTS.connectors);

            if (!data.success || !data.connectors) {
                return;
            }

            Object.keys(data.connectors).forEach(name => {
                const option = document.createElement('option');

                option.value = name;
                option.textContent = name;

                connectorSelect.appendChild(option);
            });
        } catch (error) {
            handleError('Failed to load connectors.', error);
        }
    };

    /**
     * --------------------------------------------------------------------------
     * Snapshot Creation
     * --------------------------------------------------------------------------
     */

    /**
     * Opens the snapshot creation modal.
     *
     * @param {Function} onConfirm
     */
    window.openCreateSnapshotModal = async onConfirm => {
        createSnapshotCallback = onConfirm;

        await loadConnectors();

        createSnapshotModal.style.display = 'flex';
    };

    /**
     * Creates a new snapshot.
     *
     * @param {Object} payload
     */
    async function createSnapshot(payload) {
        createSnapshotBtn.innerHTML = UI_TEXT.createLoading;
        createSnapshotBtn.disabled = true;

        try {
            const data = await fetchJson(API_ENDPOINTS.snapshots, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (data.success) {
                table.ajax.reload();
            } else {
                alert(`Failed to create snapshot: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            handleError(
                'An error occurred while creating the snapshot.',
                error
            );
        } finally {
            createSnapshotBtn.innerHTML = UI_TEXT.createDefault;
            createSnapshotBtn.disabled = false;
        }
    }

    /**
     * --------------------------------------------------------------------------
     * Snapshot Viewer
     * --------------------------------------------------------------------------
     */

    /**
     * Opens the snapshot viewer modal.
     *
     * @param {Object} snapshot
     */
    const openSnapshotViewer = snapshot => {
        currentSnapshot = snapshot;

        const devices = Object.keys(snapshot.devices);

        currentDevice = devices[0];

        renderDeviceTabs(devices);
        renderCommandTabs();
        renderCommandOutput();

        $viewSnapshotTitle.text(`Snapshot: ${snapshot.meta.name}`);
        $viewSnapshotModal.css('display', 'flex');
    };

    /**
     * Renders device tabs.
     *
     * @param {string[]} devices
     */
    const renderDeviceTabs = devices => {
        $snapshotDeviceTabs.empty();
        const deviceEntries = Object.entries(currentSnapshot.devices);
        deviceEntries.forEach(([key, device]) => {
            const activeClass = key === currentDevice ? 'active' : '';
            const displayName = device.base_prompt || key;

            $snapshotDeviceTabs.append(`
                <button
                    class="snapshot-tab ${activeClass}"
                    data-device="${key}">
                    ${displayName}
                </button>
            `);
        });
    };

    /**
     * Renders command tabs for the current device.
     */
    const renderCommandTabs = () => {
        const outputs = currentSnapshot.devices[currentDevice]?.outputs || {};
        const commands = Object.keys(outputs);

        currentCommand = commands[0];

        $snapshotCommandTabs.empty();

        commands.forEach(command => {
            const activeClass = command === currentCommand ? 'active' : '';

            $snapshotCommandTabs.append(`
                <button
                    class="snapshot-tab ${activeClass}"
                    data-command="${command}">
                    ${command}
                </button>
            `);
        });
    };

    /**
     * Renders the selected command output.
     */
    const renderCommandOutput = () => {
        const output =
            currentSnapshot.devices[currentDevice]?.outputs[currentCommand] || 'No output available.';

        $snapshotOutput.text(output);
    };

    /**
     * Resets snapshot viewer state and closes modal.
     */
    const closeSnapshotViewer = () => {
        $viewSnapshotModal.css('display', 'none');

        currentSnapshot = null;
        currentDevice = null;
        currentCommand = null;
    };

    /**
     * --------------------------------------------------------------------------
     * Event Handlers
     * --------------------------------------------------------------------------
     */

    createSnapshotBtn.addEventListener('click', () => {
        openCreateSnapshotModal(async payload => {
            await createSnapshot(payload);
        });
    });

    $('#closeCreateSnapshotModal').on('click', closeModal);

    createSnapshotModal.addEventListener('click', event => {
        if (event.target === createSnapshotModal) {
            closeModal();
        }
    });

    createSnapshotForm.addEventListener('submit', async event => {
        event.preventDefault();

        const name = document.getElementById('snapshotName').value.trim();
        const type = document.querySelector('input[name="snapshotType"]:checked').value;
        const connectorName = document.getElementById('snapshotConnector').value;
        const devices = document.getElementById('snapshotDevices').value.trim();

        if (!name) {
            alert('Please enter a name for the snapshot.');
            return;
        }

        if (!type) {
            alert('Please select a snapshot type.');
            return;
        }

        if (!connectorName) {
            alert('Please select a connector.');
            return;
        }

        if (!devices) {
            alert('Please enter at least one device.');
            return;
        }

        try {
            const data = await fetchJson(API_ENDPOINTS.connectors);

            const connector = data.connectors?.[connectorName];

            if (!connector) {
                alert('Selected connector not found.');
                return;
            }

            closeModal();

            if (typeof createSnapshotCallback === 'function') {
                createSnapshotCallback({
                    name,
                    type,
                    connector,
                    devices: devices.split('\n').map(device => device.trim()).filter(Boolean)
                });
            }
        } catch (error) {
            handleError(
                'Failed to validate selected connector.',
                error
            );
        }
    });

    /**
     * --------------------------------------------------------------------------
     * Event Delegation
     * --------------------------------------------------------------------------
     */

    // Handle checkbox selection changes dynamically
    $(document).on('change', '.row-check', updateValidateButtonVisibility);

    // Handle snapshot deletion
    $snapshotsTable.on('click', '.delete-snapshot-btn', async function () {
        const filename = $(this).data('file');

        try {
            const data = await fetchJson(API_ENDPOINTS.snapshots, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ filename })
            });

            if (data.success) {
                table.ajax.reload();
            } else {
                alert(`Failed to delete snapshot: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            handleError(
                'An error occurred while deleting the snapshot.',
                error
            );
        }
    });

    // Handle snapshot viewing
    $snapshotsTable.on('click', '.view-snapshot-btn', async function () {
        const filename = $(this).data('file');

        try {
            const snapshot = await fetchJson(
                API_ENDPOINTS.snapshotFile(filename)
            );

            if (!snapshot.success) {
                alert('Failed to load snapshot.');
                return;
            }

            openSnapshotViewer(snapshot.data);
        } catch (error) {
            handleError(
                'An error occurred while loading the snapshot.',
                error
            );
        }
    });

    // Handle snapshot downloading
    $snapshotsTable.on('click', '.download-snapshot-btn', function () {
        const filename = $(this).data('file');
        window.location.href = API_ENDPOINTS.downloadSnapshot(filename);
    });

    // Close snapshot viewer
    $('#closeViewSnapshotModal').on('click', closeSnapshotViewer);

    // Handle device tab selection
    $(document).on('click', '#snapshotDeviceTabs .snapshot-tab', function () {
        currentDevice = $(this).data('device');
        renderDeviceTabs(currentSnapshot.devices);
        renderCommandTabs();
        renderCommandOutput();
    });

    // Handle command tab selection
    $(document).on('click','#snapshotCommandTabs .snapshot-tab',function () {
        currentCommand = $(this).data('command');
        renderCommandOutput();
        $('#snapshotCommandTabs .snapshot-tab').removeClass('active');
        $(this).addClass('active');
    });

    const openValidationModal = async () => {
        const selected = $('.row-check:checked')
            .map(function () {
                return {
                    id: $(this).data('id'),
                    type: $(this).data('type')
                };
            })
            .get();

        if (selected.length !== 2) {
            alert('Please select exactly 2 snapshots.');
            return;
        }

        try {
            const preSnapshot = selected.find(s => s.type === 'pre');
            const postSnapshot = selected.find(s => s.type === 'post');

            if (!preSnapshot || !postSnapshot) {
                alert('Please select one PRE and one POST snapshot.');
                return;
            }

            const [preRes, postRes] = await Promise.all([
                fetchJson(API_ENDPOINTS.snapshotFile(preSnapshot.id)),
                fetchJson(API_ENDPOINTS.snapshotFile(postSnapshot.id))
            ]);

            const pre = preRes.data;
            const post = postRes.data;
            buildValidationModal(pre, post);
            $('#validateSnapshotsModal').css('display', 'flex');

        } catch (error) {
            handleError('Failed to load snapshots for validation.',error);
        }
    };

    const buildValidationModal = (pre, post) => {
        const preDevices = Object.keys(pre.devices);
        const postDevices = Object.keys(post.devices);

        // =========================================================
        // Endpoint Validation
        // =========================================================

        $('#endpointPreDevices').html(`
            <div class="validation-device-list">
                ${preDevices.map(device => `
                    <label class="validation-device-item">
                        <input type="checkbox"
                               value="${device}" checked>
                        ${device}
                        (${pre.meta.name})
                    </label>
                `).join('')}
            </div>
        `);

        $('#endpointPostDevices').html(`
            <div class="validation-device-list">
                ${postDevices.map(device => `
                    <label class="validation-device-item">
                        <input type="checkbox"
                               value="${device}" checked>
                        ${device}
                        (${post.meta.name})
                    </label>
                `).join('')}
            </div>
        `);

        // =========================================================
        // Route + Config Dropdowns
        // =========================================================

        const buildOptions = devices =>
            devices.map(device => `
                <option value="${device}">
                    ${device}
                </option>
            `).join('');

        $('#routePreDevice').html(buildOptions(preDevices));
        $('#routePostDevice').html(buildOptions(postDevices));

        $('#configPreDevice').html(buildOptions(preDevices));
        $('#configPostDevice').html(buildOptions(postDevices));

        // Save snapshots in modal state
        $('#validateSnapshotsModal').data('pre', pre);
        $('#validateSnapshotsModal').data('post', post);
    };

    validateBtn.addEventListener('click',openValidationModal);

    $('#closeValidateSnapshotsModal').on('click',() => {
            $('#validateSnapshotsModal').css('display', 'none');
        }
    );

    $('#confirmValidateSnapshots').on('click', async function () {
         const modal = $('#validateSnapshotsModal');
         const pre = modal.data('pre');
         const post = modal.data('post');
         const payload = {
             pre_snapshot: pre.meta.filename,
             post_snapshot: post.meta.filename,

             endpoint_validation: {
                 pre_devices: $('#endpointPreDevices input:checked')
                     .map(function () {
                         return this.value;
                     })
                     .get(),

                 post_devices: $('#endpointPostDevices input:checked')
                     .map(function () {
                         return this.value;
                     })
                     .get()
             },
             route_validation: {
                 pre_device: $('#routePreDevice').val(),
                 post_device: $('#routePostDevice').val()
             },
             config_compare: {
                 pre_device: $('#configPreDevice').val(),
                 post_device: $('#configPostDevice').val()
             }
         };
         try {
             const response = await fetchJson('/netverify/api/validate', {
                 method: 'POST',
                 headers: {
                     'Content-Type': 'application/json'
                 },
                 body: JSON.stringify(payload)
                 });

                if (response.success) {
                    $('#validateSnapshotsModal').hide();
                    $('#validationReportContainer').html(response.report.html);
                    $('#validationReportModal').css('display','flex');
                }
         } catch (error) {
            handleError('Validation failed.', error);
         }
    });

    $('#closeValidationReportModal').on('click', () => {
        $('#validationReportModal').hide();
    });

    const $reportsTable = $('#reportsTable');
    const reportsTable = $reportsTable.DataTable({
        autoWidth: false,
        ajax: {
            url: API_ENDPOINTS.reports,
            dataSrc: 'data'
        },
        columnDefs: [
            {
                targets: 1,
                width: '200px',
            }
        ],
        columns: [
            { data: 'filename' },
            { data: 'date' },
            {
                data: null,
                render: data => `
                    <div class="actions">
                        <button class="view-report-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">open_in_new</span>
                            View
                        </button>
                        <button class="download-report-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">download</span>
                            Download
                        </button>
                        <button class="delete-report-btn icon-text" data-file="${data.filename}">
                            <span class="material-icons">delete</span>
                            Delete
                        </button>
                    </div>
                `
            }
        ]
    });
    const reportsModal = document.getElementById('reportsModal');
    $('#openReportsBtn').on('click', () => {
        reportsTable.ajax.reload();
        $('#reportsModal').css('display', 'flex');
    });

    $('#closeReportsModal').on('click', () => {
        $('#reportsModal').hide();
    });

    $reportsTable.on('click', '.view-report-btn', async function () {
        const filename = $(this).data('file');
        try {
            const response = await fetchJson(API_ENDPOINTS.reportFile(filename));

            if (!response.success) {
                alert('Failed to load report.');
                return;
            }

            $('#reportsModal').hide();
            $('#validationReportContainer').html(response.html);
            $('#validationReportModal').css('display', 'flex');

        } catch (error) {
            handleError('Failed to open report.',error);
        }
    });

    $reportsTable.on('click', '.download-report-btn', function () {
        const filename = $(this).data('file');
        window.location.href = API_ENDPOINTS.downloadReport(filename);
    });

    $reportsTable.on('click', '.delete-report-btn', async function () {
        const filename = $(this).data('file');
        try {
            const response = await fetchJson(
                API_ENDPOINTS.reports,
                {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ filename })
                }
            );
            if (response.success) {
                reportsTable.ajax.reload();
            }
        } catch (error) {
            handleError('Failed to delete report.', error);
        }
    });

});