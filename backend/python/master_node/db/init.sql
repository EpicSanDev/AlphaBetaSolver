-- Initialize GTO Solver Database
-- Create database and user if running manually

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Simulations table
CREATE TABLE IF NOT EXISTS simulations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255),
    description TEXT,
    simulation_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    game_config JSONB NOT NULL,
    solver_config JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    progress FLOAT DEFAULT 0.0,
    current_iteration INTEGER DEFAULT 0,
    total_iterations INTEGER,
    exploitability FLOAT
);

-- Tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    simulation_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    assigned_node_id VARCHAR(255),
    task_data JSONB NOT NULL,
    result_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Compute nodes table
CREATE TABLE IF NOT EXISTS compute_nodes (
    id VARCHAR(255) PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    capacity INTEGER NOT NULL DEFAULT 4,
    current_tasks INTEGER DEFAULT 0,
    total_tasks_completed INTEGER DEFAULT 0,
    node_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Results table for storing strategy solutions
CREATE TABLE IF NOT EXISTS simulation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    simulation_id UUID NOT NULL REFERENCES simulations(id) ON DELETE CASCADE,
    result_type VARCHAR(50) NOT NULL, -- 'strategy', 'exploitability', 'tree'
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Metrics table for performance monitoring
CREATE TABLE IF NOT EXISTS metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    labels JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    simulation_id UUID REFERENCES simulations(id),
    node_id VARCHAR(255)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_simulations_status ON simulations(status);
CREATE INDEX IF NOT EXISTS idx_simulations_created_at ON simulations(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_simulation_id ON tasks(simulation_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_node ON tasks(assigned_node_id);
CREATE INDEX IF NOT EXISTS idx_compute_nodes_status ON compute_nodes(status);
CREATE INDEX IF NOT EXISTS idx_simulation_results_simulation_id ON simulation_results(simulation_id);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX IF NOT EXISTS idx_metrics_simulation_id ON metrics(simulation_id);

-- Triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_simulations_updated_at BEFORE UPDATE ON simulations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert default data
INSERT INTO compute_nodes (id, status, capacity) VALUES 
    ('local-node-1', 'active', 4),
    ('local-node-2', 'active', 4)
ON CONFLICT (id) DO NOTHING;
