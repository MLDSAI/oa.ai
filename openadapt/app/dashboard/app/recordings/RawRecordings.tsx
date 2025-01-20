import { SimpleTable } from '@/components/SimpleTable'
import dynamic from 'next/dynamic'
import { Recording } from '@/types/recording'
import React, { useEffect, useState } from 'react'
import { timeStampToDateString } from '../utils'
import { useRouter } from 'next/navigation'

const FramePlayer = dynamic<{ recording: Recording; frameRate: number }>(
    () => import('@/components/FramePlayer').then((mod) => mod.FramePlayer),
    { ssr: false }
)

async function fetchRecordingWithScreenshots(recordingId: string | number) {
    try {
        const response = await fetch(
            `/api/recordings/${recordingId}/screenshots`
        )
        if (!response.ok) {
            throw new Error('Failed to fetch screenshots')
        }
        const data = await response.json()
        return data.screenshots || []
    } catch (error) {
        console.error('Error fetching screenshots:', error)
        return []
    }
}

export const RawRecordings = () => {
    const [recordings, setRecordings] = useState<Recording[]>([])
    const [loading, setLoading] = useState(true)
    const router = useRouter()

    async function fetchRecordings() {
        try {
            setLoading(true)
            const res = await fetch('/api/recordings')
            if (res.ok) {
                const data = await res.json()

                // Fetch screenshots for all recordings in parallel
                const recordingsWithScreenshots = await Promise.all(
                    data.recordings.map(async (rec: Recording) => {
                        const screenshots = await fetchRecordingWithScreenshots(
                            rec.id
                        )
                        return {
                            ...rec,
                            screenshots,
                        }
                    })
                )

                setRecordings(recordingsWithScreenshots)
            }
        } catch (error) {
            console.error('Error fetching recordings:', error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchRecordings()
    }, [])

    function onClickRow(recording: Recording) {
        return () => router.push(`/recordings/detail/?id=${recording.id}`)
    }

    if (loading) {
        return <div className="text-center py-4">Loading recordings...</div>
    }

    return (
        <SimpleTable
            columns={[
                { name: 'ID', accessor: 'id' },
                { name: 'Description', accessor: 'task_description' },
                {
                    name: 'Start time',
                    accessor: (recording: Recording) =>
                        recording.video_start_time
                            ? timeStampToDateString(recording.video_start_time)
                            : 'N/A',
                },
                {
                    name: 'Monitor Width/Height',
                    accessor: (recording: Recording) =>
                        `${recording.monitor_width}/${recording.monitor_height}`,
                },
                {
                    name: 'Video',
                    accessor: (recording: Recording) => (
                        <div className="min-w-[200px]">
                            <FramePlayer recording={recording} frameRate={1} />
                        </div>
                    ),
                },
            ]}
            data={recordings}
            refreshData={fetchRecordings}
            onClickRow={onClickRow}
        />
    )
}
