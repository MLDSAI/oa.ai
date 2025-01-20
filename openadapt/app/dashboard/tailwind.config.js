/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        './components/**/*.{js,ts,jsx,tsx,mdx}',
        './app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            backgroundImage: {
                'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
                'gradient-conic':
                    'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
            },
            fontSize: {
                sm: '0.750rem',
                base: '1rem',
                xl: '1.333rem',
                '2xl': '1.777rem',
                '3xl': '2.369rem',
                '4xl': '3.158rem',
                '5xl': '4.210rem',
            },
            fontFamily: {
                heading: ['var(--font-poppins)'],
                body: ['var(--font-poppins)'],
            },
            fontWeight: {
                normal: '400',
                bold: '700',
            },
            colors: {
                text: '#e7e5e4',
                background: '#00001f',
                primary: '#2f27ce',
                secondary: '#6259a1',
                accent: '#6c78f9',
            },
        },
    },
    plugins: [],
}
