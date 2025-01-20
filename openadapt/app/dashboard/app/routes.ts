import {
    IconFileText,
    IconSettings,
    IconEraser,
    IconBook,
} from '@tabler/icons-react'

export interface Route {
    name: string
    path: string
    icon: typeof IconFileText // Simple type that works for all Tabler icons
    active?: boolean
    badge?: string | number
}

export const routes: Route[] = [
    {
        name: 'Recordings',
        path: '/recordings',
        icon: IconFileText,
        active: true,
    },
    {
        name: 'Settings',
        path: '/settings',
        icon: IconSettings,
        active: false,
    },
    {
        name: 'Scrubbing',
        path: '/scrubbing',
        icon: IconEraser,
        active: false,
    },
    {
        name: 'Onboarding',
        path: '/onboarding',
        icon: IconBook,
        active: false,
    },
]
