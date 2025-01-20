'use client'

import { Stack } from '@mantine/core'
import { IconChevronRight } from '@tabler/icons-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import React from 'react'

type Props = {
    routes: { name: string; path: string }[]
}

export const Navbar = ({ routes }: Props) => {
    const currentRoute = usePathname()
    return (
        <Stack gap={0}>
            {routes.map((route) => (
                <Link
                    href={route.path}
                    key={route.path}
                    className={
                        (currentRoute === route.path
                            ? 'bg-gray-300 rounded-lg'
                            : '') +
                        ' p-5 no-underline flex items-center gap-x-1 transition hover:gap-x-2 ease-out'
                    }
                >
                    {route.name} <IconChevronRight size={20} />
                </Link>
            ))}
        </Stack>
    )
}
