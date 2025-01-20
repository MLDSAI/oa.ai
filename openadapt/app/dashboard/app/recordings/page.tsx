'use client';

import { Box, Button, Tabs } from "@mantine/core";
import { useEffect, useState } from "react";
import { RecordingStatus } from "@/types/recording";
import { ScrubbedRecordings } from "./ScrubbedRecordings";
import { RawRecordings } from "./RawRecordings";


export default function Recordings() {
    const [recordingStatus, setRecordingStatus] = useState(RecordingStatus.UNKNOWN);
    function startRecording() {
        if (recordingStatus === RecordingStatus.RECORDING) {
            return;
        }
        fetch('/api/recordings/start').then(res => {
            if (res.ok) {
                setRecordingStatus(RecordingStatus.RECORDING);
            }
        });
    }
    function stopRecording() {
        if (recordingStatus === RecordingStatus.STOPPED) {
            return;
        }
        setRecordingStatus(RecordingStatus.UNKNOWN);
        fetch('/api/recordings/stop').then(res => {
            if (res.ok) {
                setRecordingStatus(RecordingStatus.STOPPED);
            }
        });
    }

    function fetchRecordingStatus() {
        fetch('/api/recordings/status').then(res => {
            if (res.ok) {
                res.json().then((data) => {
                    if (data.recording) {
                        setRecordingStatus(RecordingStatus.RECORDING);
                    } else {
                        setRecordingStatus(RecordingStatus.STOPPED);
                    }
                });
            }
        });
    }

    useEffect(() => {
        fetchRecordingStatus();
    }, []);
    return (
        <Box>
            {recordingStatus === RecordingStatus.RECORDING && (
                <Button onClick={stopRecording} variant="outline" className="hover:bg-red-900 bg-red-600 hover:text-zinc-100 text-zinc-200 hover:text-white">
                    Stop recording
                </Button>
            )}
            {recordingStatus === RecordingStatus.STOPPED && (
                <Button onClick={startRecording} variant="outline" className="hover:bg-accent bg-primary/80 hover:text-zinc-100 text-zinc-200 hover:text-white">
                    Start recording
                </Button>
            )}
            {recordingStatus === RecordingStatus.UNKNOWN && (
                <Button variant="outline" color="blue">
                    Loading recording status...
                </Button>
            )}
            <Tabs defaultValue="regular" mt={40}>
                <Tabs.List>
                    <Tabs.Tab value="regular">
                        Recordings
                    </Tabs.Tab>
                    <Tabs.Tab value="scrubbed">
                        Scrubbed recordings
                    </Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="regular" mt={40}>
                    <RawRecordings />
                </Tabs.Panel>
                <Tabs.Panel value="scrubbed" mt={40}>
                    <ScrubbedRecordings />
                </Tabs.Panel>
            </Tabs>
        </Box>
    )
}
