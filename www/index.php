<?php
// Colorlight Manager - Phase 2 dashboard (read-only discovery only).

$interfaces = array();
foreach (glob('/sys/class/net/*') as $path) {
    $name = basename($path);
    if ($name === 'lo') {
        continue;
    }
    $interfaces[] = $name;
}
sort($interfaces);
?>
<style>
.colorlightManager { max-width: 900px; }
.colorlightManager .phaseNote { color: #666; font-style: italic; margin-bottom: 1em; }
.colorlightManager .scanControls { display: flex; align-items: center; gap: 0.5em; margin-bottom: 1em; flex-wrap: wrap; }
.clmTable { width: 100%; border-collapse: collapse; }
.clmTable th, .clmTable td { border: 1px solid #ccc; padding: 0.4em 0.6em; text-align: left; }
.clmTable .unverifiedValue { color: #a66a00; }
.clmTable .unverifiedValue::after { content: " (unverified)"; font-size: 0.85em; color: #999; }
</style>

<div class="colorlightManager">
    <h2>Colorlight Manager</h2>
    <p class="phaseNote">
        Phase 2 (read-only discovery). This page only sends Colorlight's
        broadcast discovery query and shows what receivers reply with - it
        does not read, back up, import, or write any receiver configuration.
    </p>

    <div class="scanControls">
        <label for="clmIface">Interface:</label>
        <select id="clmIface">
<?php foreach ($interfaces as $iface) : ?>
            <option value="<?php echo htmlspecialchars($iface); ?>"><?php echo htmlspecialchars($iface); ?></option>
<?php endforeach; ?>
        </select>
        <button id="clmScanButton" type="button">Scan for Receivers</button>
        <span id="clmStatus"></span>
    </div>

    <table id="clmResults" class="clmTable" style="display:none;">
        <thead>
            <tr>
                <th>Receiver ID</th>
                <th>Firmware</th>
                <th>Uptime</th>
                <th>Packets</th>
                <th>Source MAC</th>
                <th>Cabinet W&times;H (unverified)</th>
            </tr>
        </thead>
        <tbody></tbody>
    </table>
</div>

<script>
(function () {
    'use strict';

    const CLM_PLUGIN_BASE =
        (typeof pluginBase !== 'undefined' && pluginBase)
            ? pluginBase
            : 'plugin.php?plugin=fpp-colorlight-manager&';
    const CLM_BASE = CLM_PLUGIN_BASE + 'nopage=1&page=';

    function clmUrl(rel) {
        return CLM_BASE + 'www/' + rel;
    }

    function msToHuman(ms) {
        var totalSeconds = Math.floor(ms / 1000);
        var hours = Math.floor(totalSeconds / 3600);
        var minutes = Math.floor((totalSeconds % 3600) / 60);
        var seconds = totalSeconds % 60;
        return hours + 'h ' + minutes + 'm ' + seconds + 's';
    }

    function renderResults(receivers) {
        var table = document.getElementById('clmResults');
        var tbody = table.querySelector('tbody');
        tbody.innerHTML = '';

        if (!receivers || receivers.length === 0) {
            table.style.display = 'none';
            document.getElementById('clmStatus').textContent = 'No receivers found.';
            return;
        }

        receivers.forEach(function (r) {
            var row = document.createElement('tr');

            [r.receiverId, r.firmwareVersion, msToHuman(r.uptimeMs), r.packetCount, r.sourceMac]
                .forEach(function (value) {
                    var td = document.createElement('td');
                    td.textContent = value;
                    row.appendChild(td);
                });

            var cabinetTd = document.createElement('td');
            cabinetTd.className = 'unverifiedValue';
            var width = r.fields && r.fields.cabinetWidth ? r.fields.cabinetWidth.value : '?';
            var height = r.fields && r.fields.cabinetHeight ? r.fields.cabinetHeight.value : '?';
            cabinetTd.textContent = width + '×' + height;
            row.appendChild(cabinetTd);

            tbody.appendChild(row);
        });

        table.style.display = '';
        document.getElementById('clmStatus').textContent = 'Found ' + receivers.length + ' receiver(s).';
    }

    function scan() {
        var iface = document.getElementById('clmIface').value;
        var status = document.getElementById('clmStatus');
        var button = document.getElementById('clmScanButton');

        button.disabled = true;
        status.textContent = 'Scanning ' + iface + ' ...';

        fetch(clmUrl('discover.php') + '&iface=' + encodeURIComponent(iface), { cache: 'no-store' })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.error) {
                    status.textContent = 'Error: ' + (data.message || data.error);
                    return;
                }
                renderResults(data.receivers);
            })
            .catch(function (err) {
                status.textContent = 'Request failed: ' + err;
            })
            .finally(function () {
                button.disabled = false;
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var button = document.getElementById('clmScanButton');
        if (button) {
            button.addEventListener('click', scan);
        }
    });
})();
</script>
