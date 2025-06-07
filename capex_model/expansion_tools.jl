"""
Capacity expansion modules
"""

function load(model_name)
    # Path to model inputs
    inputs_dir = joinpath(pwd(), "models", model_name, "inputs")

    # Load each of the input files
    buses = CSV.read(joinpath(inputs_dir, "buses.csv"), DataFrame);
    lines = CSV.read(joinpath(inputs_dir, "lines.csv"), DataFrame);
    gens = CSV.read(joinpath(inputs_dir, "generators.csv"), DataFrame);
    loads = CSV.read(joinpath(inputs_dir, "loads.csv"), DataFrame);
    variability = CSV.read(joinpath(inputs_dir, "variability.csv"), DataFrame);

    # Create representative periods
    
    # Time periods sampled in the original frame
    periods = [collect(1:24*7), collect(2000:(2000+24*7))]
    T = collect(Iterators.flatten(periods))  # Set of all time periods to sample
    
    # Select periods from loads
    loads = loads[:, 2:8761][:, T]
    variability = variability[:, 2:8760][:, T]

    # Convert P to be in the same index set as the model
    p_start = 1
    P = []
    for P_i in periods
        p_end = length(P_i)
        
        push!(P, collect(p_start:p_end+p_start-1))
        p_start = p_start + p_end
    end

    return (buses, lines, gens, loads, variability, P)
end


function run_model(load, model, save, model_name, senario_name)
    """
    model: Function that runs capacity expansion
    
    model_name: Name under which to save outputs
    """
    
    (buses, lines, gens, loads, variability, P) = load(model_name)
    
    model_solved = model(buses, lines, gens, loads, variability, P)
     
    save(model_solved, model_name, senario_name,
        buses, lines, gens, loads)
end


function save(model, model_name, senario_name,
        buses, lines, gens, loads)
    """
    Save model outputs as a CSV
    """
    function table(name, value_type)
        """
        Helper function to read a model variable or 
        constraint and return values as a time indexed 
        dataframe
        """
        df = DataFrame(value_type.(model[name]).data, :auto)
        rename!(df, t_cols)
    end

    # Create outputs folder (if one does not already exist)
    outputs_dir = joinpath(pwd(), "models", model_name, "outputs", senario_name)
    if !(isdir(outputs_dir))
    	mkdir(outputs_dir)
    end
    
    # Datetimes of columns in the loads dataset
    t_cols = names(loads)

    # Get generation data
    sol_gen = table(:GEN, value)
    sol_gen = hcat(sol_gen, gens[:, [:gen_id, :bus, :fueltype]]);
    # Get load sheding data 
    sol_shed = table(:SHED, value)
    sol_shed[:, :gen_id] .= -1
    sol_shed[:, :bus] = 1:nrow(sol_shed)
    sol_shed[:, :fueltype] .= "Load Shed"
    # Join load sheding and generation
    sol_gen = vcat(sol_gen, sol_shed)

    # Get prices at each node
    sol_price = table(:cBalance, dual)

    # Write results
    CSV.write(joinpath(outputs_dir, "generation.csv"), sol_gen)
    CSV.write(joinpath(outputs_dir, "prices.csv"), sol_price)
end