<?php
// Runs the Phase 2 discovery backend for the requested interface and
// returns its JSON output as-is. Read-only: sends broadcast discovery
// frames and parses replies, nothing is written to any receiver.

header('Content-Type: application/json');

$iface = isset($_GET['iface']) ? $_GET['iface'] : '';

// Only allow interface names that look like real Linux netdev names -
// this value is passed to a shelled-out command, so validate strictly
// rather than trying to escape an arbitrary string.
if (!preg_match('/^[a-zA-Z0-9_.:-]{1,15}$/', $iface)) {
    http_response_code(400);
    echo json_encode(array('error' => 'invalid_interface'));
    exit;
}

if (!is_dir('/sys/class/net/' . $iface)) {
    http_response_code(400);
    echo json_encode(array('error' => 'unknown_interface'));
    exit;
}

$pluginDir = dirname(__DIR__);
$script = $pluginDir . '/backend/receiver_discovery.py';

$cmd = 'sudo /usr/bin/env python3 ' . escapeshellarg($script) .
       ' --iface ' . escapeshellarg($iface) . ' --json 2>&1';

exec($cmd, $output, $returnCode);
$json = implode("\n", $output);

if ($returnCode !== 0) {
    http_response_code(500);
    // $json may already be a JSON error payload from the script, or plain
    // stderr text (e.g. sudoers misconfiguration) - wrap either case.
    $decoded = json_decode($json, true);
    if ($decoded === null) {
        echo json_encode(array('error' => 'discovery_failed', 'message' => $json));
    } else {
        echo json_encode($decoded);
    }
    exit;
}

echo $json;
