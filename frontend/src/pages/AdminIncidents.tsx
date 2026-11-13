import { TicketList } from '../components/TicketList';

export const AdminIncidents = () => (
  <TicketList
    scope="all"
    title="All Incidents"
    subtitle="Organization-wide incident queue. Open a ticket to update status, assignment and resolution."
  />
);
