'use client';

import { ActionEvents } from "@/components/ActionEvent/ActionEvents";
import { RecordingDetails } from "@/components/RecordingDetails";
import { ActionEvent as ActionEventType } from "@/types/action-event";
import { Recording as RecordingType } from "@/types/recording";
import { Box, Loader, Progress } from "@mantine/core";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function Recording() {
    const searchParams = useSearchParams();
    const id = searchParams.get("id");
    const [recordingInfo, setRecordingInfo] = useState<{
        recording: RecordingType,
        action_events: ActionEventType[],
        num_events: number,
    }>();
    useEffect(() => {
        if (!id) {
            return;
        }
        const websocket = new WebSocket(`ws://${window.location.host}/api/recordings/${id}`);
        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "recording") {
                setRecordingInfo(prev => {
                    if (!prev) {
                        return {
                            "recording": data.value,
                            "action_events": [],
                            "num_events": 0,
                        }
                    }
                    return prev;
                });
            } else if (data.type === "action_event") {
                setRecordingInfo(prev => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        "action_events": [...prev.action_events, modifyActionEvent(data.value, prev.recording.original_recording_id === null)],
                    }
                });
            } else if (data.type === "num_events") {
                setRecordingInfo(prev => {
                    if (!prev) return prev;
                    return {
                        ...prev,
                        "num_events": data.value,
                    }
                });
            }
        }

        return () => {
            websocket.close();
        }
    }, [id]);
    if (!recordingInfo) {
        return <Loader />;
    }
    const actionEvents = recordingInfo.action_events;

    return (
        <Box>
            <RecordingDetails recording={recordingInfo.recording} />
            {actionEvents.length && actionEvents.length < recordingInfo.num_events && (
                <Progress.Root size={30} my={30}>
                    <Progress.Section value={(actionEvents.length / recordingInfo.num_events) * 100}>
                        <Progress.Label>Loading events {actionEvents.length}/{recordingInfo.num_events}</Progress.Label>
                    </Progress.Section>
                </Progress.Root>
            )}
            <ActionEvents events={actionEvents} />
        </Box>
    )
}

function modifyActionEvent(actionEvent: ActionEventType, isOriginal: boolean): ActionEventType {
    let children = actionEvent.children;
    if (actionEvent.children) {
        children = actionEvent.children.map(child => modifyActionEvent(child, isOriginal));
    }
    let id = actionEvent.id;
    let isComputed = false;
    if (!id) {
        // this is usually the case, when new events like 'singleclick'
        // or 'doubleclick' are created while merging several events together,
        // but they are not saved in the database
        id = crypto.randomUUID();
        isComputed = true;
    }
    return {
        ...actionEvent,
        id,
        children,
        isComputed,
        isOriginal,
        summary: actionEvent.summary,
        icon: actionEvent.icon,
    }
}


export default function RecordingPage() {
    return (
        <Suspense>
            <Recording />
        </Suspense>
    )
}
