import { TicketList } from '../components/TicketList';

export const MyTickets = () => (
  <TicketList
    scope="mine"
    title="My Tickets"
    subtitle="Every incident and request you have submitted to IT."
  />
);
