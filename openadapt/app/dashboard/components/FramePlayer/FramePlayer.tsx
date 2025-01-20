'use client'

import { Recording } from '@/types/recording'
import React, { useEffect, useRef, useState } from 'react'
import { Stage, Layer, Image as KonvaImage, Group, Rect } from 'react-konva'
import Konva from 'konva'

interface FramePlayerProps {
    recording: Recording
    frameRate: number
}

export const FramePlayer: React.FC<FramePlayerProps> = ({
    recording,
    frameRate,
}) => {
    const [currentScreenshotIndex, setCurrentScreenshotIndex] = useState(0)
    const [currentImage, setCurrentImage] = useState<HTMLImageElement | null>(
        null
    )
    const [isHovering, setIsHovering] = useState(false)
    const imageRef = useRef<Konva.Image>(null)
    const intervalRef = useRef<NodeJS.Timeout | null>(null)

    const STAGE_WIDTH = 300
    const STAGE_HEIGHT = 200
    const CORNER_RADIUS = 8

    // Load initial image
    useEffect(() => {
        if (!recording?.screenshots?.length) return

        const img = new window.Image()
        img.src = recording.screenshots[0]
        img.onload = () => {
            setCurrentImage(img)
        }
    }, [recording])

    useEffect(() => {
        if (!recording?.screenshots?.length) {
            if (isHovering && currentScreenshotIndex !== 0) {
                setCurrentScreenshotIndex(0)
            }
            return
        }

        intervalRef.current = setInterval(() => {
            setCurrentScreenshotIndex((prevIndex) => {
                return (prevIndex + 1) % recording.screenshots.length
            })
        }, 1000 / frameRate)

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current)
            }
        }
    }, [recording, frameRate, isHovering])

    // Handle image loading when screenshot index changes
    useEffect(() => {
        if (!recording?.screenshots?.length) return

        const img = new window.Image()
        img.src = recording.screenshots[currentScreenshotIndex]
        img.onload = () => {
            setCurrentImage(img)
        }
    }, [currentScreenshotIndex, recording])

    if (!recording?.screenshots?.length) {
        return (
            <div className="flex items-center justify-center w-full h-[150px] bg-gray-100 rounded-lg">
                <span className="text-sm text-gray-500">No screenshots</span>
            </div>
        )
    }

    return (
        <div
            className="relative cursor-pointer"
            onMouseEnter={() => setIsHovering(true)}
            onMouseLeave={() => {
                setIsHovering(false)
                setCurrentScreenshotIndex(0)
            }}
        >
            <Stage width={STAGE_WIDTH} height={STAGE_HEIGHT}>
                <Layer>
                    <Group
                        clipFunc={(ctx) => {
                            ctx.beginPath()
                            ctx.moveTo(CORNER_RADIUS, 0)
                            ctx.lineTo(STAGE_WIDTH - CORNER_RADIUS, 0)
                            ctx.quadraticCurveTo(
                                STAGE_WIDTH,
                                0,
                                STAGE_WIDTH,
                                CORNER_RADIUS
                            )
                            ctx.lineTo(
                                STAGE_WIDTH,
                                STAGE_HEIGHT - CORNER_RADIUS
                            )
                            ctx.quadraticCurveTo(
                                STAGE_WIDTH,
                                STAGE_HEIGHT,
                                STAGE_WIDTH - CORNER_RADIUS,
                                STAGE_HEIGHT
                            )
                            ctx.lineTo(CORNER_RADIUS, STAGE_HEIGHT)
                            ctx.quadraticCurveTo(
                                0,
                                STAGE_HEIGHT,
                                0,
                                STAGE_HEIGHT - CORNER_RADIUS
                            )
                            ctx.lineTo(0, CORNER_RADIUS)
                            ctx.quadraticCurveTo(0, 0, CORNER_RADIUS, 0)
                            ctx.closePath()
                        }}
                    >
                        {currentImage && (
                            <KonvaImage
                                ref={imageRef}
                                image={currentImage}
                                width={STAGE_WIDTH}
                                height={STAGE_HEIGHT}
                                listening={false}
                            />
                        )}
                    </Group>
                </Layer>
            </Stage>
            {!isHovering && (
                <div className="absolute bottom-1 left-1 right-1 flex justify-between text-xs text-white bg-black/50 px-2 py-0.5 rounded w-fit">
                    <span>
                        Frame {currentScreenshotIndex + 1}/
                        {recording.screenshots.length}
                    </span>
                </div>
            )}
        </div>
    )
}
