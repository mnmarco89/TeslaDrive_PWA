const paths = {
  home: 'M3 10 12 3l9 7v11h-6v-7H9v7H3V10Z',
  lock: 'M5 10h14v11H5V10Zm3 0V6a4 4 0 0 1 8 0v4M12 14v3',
  unlock: 'M5 10h14v11H5V10Zm3 0V6a4 4 0 0 1 8 0M12 14v3',
  climate: 'M12 2v20M3.3 7l17.4 10M3.3 17 20.7 7M9 4l3 3 3-3M9 20l3-3 3 3',
  car: 'M4 10 6 4h12l2 6M3 10h18v9H3v-9Zm2 9v3m14-3v3M6 14h2m8 0h2',
  temp: 'M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0ZM12 8v10',

  charge: 'M13 2 4 14h7l-1 8 10-12h-7l1-8Z',
  route: 'M5 3a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm14 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4ZM5 7v5a3 3 0 0 0 3 3h8a3 3 0 0 0 0-6h-4M19 17v-2',
  wallet: 'M3 6h16v14H3V6Zm0 0V4h13v2m0 6h5v4h-5v-4Z',
  battery: 'M2 7h18v10H2V7Zm20 3v4M5 10v4m4-4v4m4-4v4',
  speed: 'M3 18a10 10 0 1 1 18 0M12 14l5-5M6 18h12',
  pin: 'M12 22s8-8 8-14A8 8 0 0 0 4 8c0 6 8 14 8 14ZM12 5a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
  fuel: 'M4 21V3h9v18M2 21h13M4 10h9m0 4h3v4a2 2 0 0 0 4 0V8l-3-3m1 1v4h2',
};
export default function Icon({ name = 'charge' }) {
 return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.charge}/></svg>;
}
