import { useState, useEffect } from 'react'
import { AlertTriangle, CheckCircle, Clock, PlayCircle, XCircle } from 'lucide-react'
import { format } from 'date-fns'
import { incidentsAPI } from '../services/api'

export default function Incidents() {
  const [incidents, setIncidents] = useState([])
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [filter, setFilter] = useState('all')
  const [isLoading, setIsLoading] = useState(true)

  // Fetch incidents from backend
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        const response = await incidentsAPI.list()
        const data = response.data.incidents || []
        setIncidents(data)
      } catch (err) {
        console.error('Failed to fetch incidents:', err)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchIncidents()
    // Poll for updates every 10 seconds
    const interval = setInterval(fetchIncidents, 10000)
    return () => clearInterval(interval)
  }, [])

  const filteredIncidents = filter === 'all' 
    ? incidents
    : incidents.filter(inc => inc.status === filter)

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-3">
            <span className="h-px flex-1 max-w-[60px] bg-border"></span>
            <span className="font-mono text-xs font-medium uppercase tracking-widest text-accent">
              Incident Management
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-serif text-3xl font-semibold text-foreground tracking-tight">
                Incidents
              </h1>
              <p className="text-muted-foreground mt-2">Track and resolve system incidents</p>
            </div>
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="bg-card border border-border text-foreground text-sm rounded-lg px-4 py-2.5 shadow-soft focus:outline-none focus:border-accent"
            >
              <option value="all">All Status</option>
              <option value="open">Open</option>
              <option value="investigating">Investigating</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
        </div>

        <div className="flex gap-6">
          {/* Incident List */}
          <div className="flex-1 space-y-4">
            {isLoading ? (
              <div className="text-center py-16 text-muted-foreground">Loading incidents...</div>
            ) : filteredIncidents.length === 0 ? (
              <div className="text-center py-16 bg-card rounded-lg shadow-soft border border-border">
                <AlertTriangle className="w-10 h-10 text-border mx-auto mb-3" />
                <p className="text-muted-foreground">No incidents found</p>
              </div>
            ) : (
              filteredIncidents.map((incident) => (
                <IncidentCard
                  key={incident.incident_id || incident.id}
                  incident={incident}
                  isSelected={selectedIncident?.id === incident.id}
                  onClick={() => setSelectedIncident(incident)}
                />
              ))
            )}
          </div>

          {/* Incident Details */}
          {selectedIncident && (
            <div className="w-[480px] flex-shrink-0 bg-card border border-border rounded-lg shadow-soft overflow-y-auto max-h-[calc(100vh-12rem)]">
              <IncidentDetails 
                incident={selectedIncident} 
                onClose={() => setSelectedIncident(null)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function IncidentCard({ incident, isSelected, onClick }) {
  const getSeverityColor = () => {
    switch (incident.severity) {
      case 'high': return 'border-danger-500 bg-danger-50'
      case 'medium': return 'border-warning-500 bg-warning-50'
      case 'low': return 'border-warning-500/50 bg-warning-50/50'
      default: return 'border-border bg-muted'
    }
  }

  const getStatusIcon = () => {
    switch (incident.status) {
      case 'open': return <AlertTriangle className="w-5 h-5 text-danger-500" />
      case 'investigating': return <Clock className="w-5 h-5 text-warning-500" />
      case 'resolved': return <CheckCircle className="w-5 h-5 text-success-500" />
      default: return <AlertTriangle className="w-5 h-5 text-muted-foreground" />
    }
  }

  return (
    <div 
      onClick={onClick}
      className={`p-5 rounded-lg border-2 cursor-pointer transition-all duration-200 ${
        isSelected 
          ? 'border-accent bg-accent/5 shadow-medium' 
          : `${getSeverityColor()} hover:shadow-medium`
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-start space-x-3">
          {getStatusIcon()}
          <div>
            <div className="text-foreground font-semibold">{incident.title}</div>
            <div className="text-sm text-muted-foreground mt-1">{incident.description}</div>
          </div>
        </div>
        <span className={`text-xs uppercase font-semibold px-3 py-1.5 rounded-lg border ${
          incident.severity === 'high' ? 'bg-danger-50 text-danger-600 border-danger-500/20' :
          incident.severity === 'medium' ? 'bg-warning-50 text-warning-600 border-warning-500/20' :
          'bg-warning-50/50 text-warning-600 border-warning-500/20'
        }`}>
          {incident.severity}
        </span>
      </div>
      
      <div className="flex items-center space-x-4 mt-3 text-xs text-muted-foreground">
        <span>{incident.id}</span>
        <span>•</span>
        <span>{incident.detectedBy}</span>
        <span>•</span>
        <span>{format(incident.createdAt, 'MMM d, HH:mm')}</span>
      </div>
    </div>
  )
}

function IncidentDetails({ incident, onClose }) {
  return (
    <div className="p-6">
      <div className="flex items-start justify-between mb-6 pb-4 border-b border-border">
        <div>
          <h3 className="font-serif text-xl font-semibold text-foreground">{incident.title}</h3>
          <p className="text-sm text-muted-foreground mt-1 font-mono">{incident.id}</p>
        </div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors">✕</button>
      </div>

      <div className="space-y-6">
        <div>
          <label className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Status</label>
          <div className="mt-2">
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border capitalize ${
              incident.status === 'open' ? 'bg-danger-50 text-danger-600 border-danger-500/20' :
              incident.status === 'investigating' ? 'bg-warning-50 text-warning-600 border-warning-500/20' :
              'bg-success-50 text-success-600 border-success-500/20'
            }`}>
              <div className="w-1.5 h-1.5 rounded-full bg-current"></div>
              {incident.status}
            </span>
          </div>
        </div>

        <div>
          <label className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Severity</label>
          <div className="mt-2 text-foreground capitalize font-medium">{incident.severity}</div>
        </div>

        <div>
          <label className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Description</label>
          <div className="mt-2 text-foreground text-sm leading-relaxed">{incident.description}</div>
        </div>

        <div>
          <label className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Affected Components</label>
          <div className="mt-2 flex flex-wrap gap-2">
            {(incident.affectedComponents || []).map((comp, idx) => (
              <span key={idx} className="px-3 py-1.5 bg-muted text-muted-foreground text-sm rounded-lg border border-border">
                {comp}
              </span>
            ))}
          </div>
        </div>

        <div>
          <label className="font-mono text-[10px] font-medium text-muted-foreground uppercase tracking-widest">Timeline</label>
          <div className="mt-3 space-y-3">
            <TimelineItem
              icon={<AlertTriangle className="w-4 h-4 text-danger-500" />}
              title="Incident Detected"
              description={`By ${incident.detectedBy}`}
              time={incident.createdAt}
            />
            {incident.status === 'investigating' && (
              <TimelineItem
                icon={<Clock className="w-4 h-4 text-warning-500" />}
                title="Investigation Started"
                description="Root cause analysis in progress"
                time={new Date(incident.createdAt.getTime() + 5 * 60000)}
              />
            )}
            {incident.resolvedAt && (
              <TimelineItem
                icon={<CheckCircle className="w-4 h-4 text-success-500" />}
                title="Incident Resolved"
                description="Automatic remediation applied"
                time={incident.resolvedAt}
              />
            )}
          </div>
        </div>

        <div className="pt-4 border-t border-border space-y-3">
          <button className="w-full bg-accent hover:bg-accent-secondary text-accent-foreground py-2.5 px-4 rounded-lg font-medium shadow-accent hover:shadow-hard transition-all duration-200 flex items-center justify-center gap-2">
            <PlayCircle className="w-4 h-4" />
            <span>Propose Remediation</span>
          </button>
          <button className="w-full bg-card border border-border hover:border-accent text-foreground hover:text-accent py-2.5 px-4 rounded-lg font-medium shadow-soft hover:shadow-medium transition-all duration-200 flex items-center justify-center gap-2">
            <XCircle className="w-4 h-4" />
            <span>Close Incident</span>
          </button>
        </div>
      </div>
    </div>
  )
}

function TimelineItem({ icon, title, description, time }) {
  return (
    <div className="flex space-x-3">
      <div className="flex-shrink-0 mt-1">{icon}</div>
      <div className="flex-1">
        <div className="text-foreground text-sm font-medium">{title}</div>
        <div className="text-muted-foreground text-xs mt-0.5">{description}</div>
        <div className="text-muted-foreground/60 text-xs mt-1">
          {format(time, 'MMM d, yyyy HH:mm:ss')}
        </div>
      </div>
    </div>
  )
}
