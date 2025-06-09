function expansion(buses, lines, gens, loads, variability, P, W)
    """
    Solve capacity expansion with CATS.
    
    Inputs:
        buses -- dataframe with bus types and loads
        lines -- dataframe with transmission lines info
        gens -- dataframe with generator info and costs
        loads -- 
        variability --
        P --
    """   
    #### HELPER FUNCTIONS ####
    # Select a line column using i and j 
    line = (i, j, col) -> lines[lines_map[(i, j)], col]
    # Subset of all lines connected to bus i
    J = i -> lines.t_bus[lines.f_bus .== i]
    # Select all generators in G connected to bus i
    sel = (G, i) -> collect(G)[gens[collect(G),:bus] .== i]

    function prev(t)
        """
        Returns the t-1 index using wrapping to ensure
        that if t-1 ∉ P then the largest t ∈ P is returned.
        """
        P_i = findfirst(P_i -> t in P_i, P)
        shift = first(P[P_i])
        p = length(P[P_i])
        return mod1(t - shift, p) + shift - 1
    end

    function capacity(g)
        """
        Returns capacity of generator g
        """
        return gens[g,:pmax] + (g ∈ G_new ? CATS_Model[:CAP][g] : 0)
    end

    function status(i,j,t)
        """
        Returns 1 if line (i,j) is energized at time t
        and 0 if the line is de-energized
        """
        if t in T[1:end-24]
            return 1
        else
            return line(i,j,:on)
        end
    end
    
    ##### SETS ####
    
    # Generators #
    G = gens[:, :gen_id]
    G_new = gens[gens.canidate .==1, :gen_id]
    G_ess = gens[gens.ess .== 1, :gen_id]
    G_solar = gens[gens.fueltype .== "Solar Photovoltaic", :gen_id]
    
    # Lines and Buses #
    N = 1:nrow(buses)
    L = collect(zip(lines.f_bus, lines.t_bus))
        
    # Time Periods #
    T = 1:ncol(loads)            

    #### GLOBALS ####
    # Mapping from (i, j) tuple to line index l
    lines_map = Dict(zip(L, 1:length(L)))
    
    #### PARAMETERS ####
    θlim = π*(60/180)  # Absolute max angle limit in rad
    slack_bus = 416    # Set slack bus to one with many CTs
    
    storage_hrs = 4    # Storage Hours * Power Capacity = Energy capacity ∀ g ∈ G_s
    η_charge = 0.97    # Charging efficiency  
    η_discharge = 0.91 # Discharging efficiecy
    
    # Parameters for investment #
    shed_cost = 9000 
    solar_cost = 85_000
    battery_cost = 110_000 # Assuming 4 hour storage
    budget = 100*1e6 # Budget in dollars

    ########################
    #####     MODEL    #####
    ########################
    
    CATS_Model = Model(() -> Gurobi.Optimizer())
    
    # Decision variables   
    @variables(CATS_Model, begin
        GEN[G,T] ≥ 0        # Generation of each generator 
        SHED[N,T] ≥ 0       # Load sheading at bus N
        THETA[N,T]          # Voltage phase angle of bus
        FLOW[L,T]           # Flows between all pairs of nodes
        SOC[G_ess,T] ≥ 0    # ESS state of charge
        CHARGE[G_ess,T] ≥ 0 # Chargeing of ESS 
        CAP[G_new] ≥ 0      # New capacity for each canidate site
    end)
    println("Model init okay.")
    # Max generation constraint
    @constraint(CATS_Model, cMaxGen[g ∈ G, t ∈ T], 
        GEN[g,t] ≤ variability[g,t]*capacity(g)
    )
    # Max load shedding constraint
    @constraint(CATS_Model, cMaxShed[i ∈ N, t ∈ T], 
        SHED[i,t] ≤ loads[i,t]
    )
    # Max amount of new capacity for each canidate site
    # @constraint(CATS_Model, cMaxCapSolar[g ∈ intersect(G_new, G_solar)],
    #     CAP[g] ≤ max_solar_cap
    # )
    # @constraint(CATS_Model, cMaxCapStorage[g ∈ intersect(G_new, G_ess)],
    #     CAP[g] ≤ max_battery_cap
    # )   
    println("Max constraints okay.")
    #########################
    #### BATTERY STORAGE ####
    #########################
    # Charging must be less than max power capacity
    @constraint(CATS_Model, cMaxCharge[g ∈ G_ess, t ∈ T], 
        CHARGE[g,t] ≤ capacity(g)
    )
    
    # Energy capacity must be less ×4 the power capacity
    @constraint(CATS_Model, cMaxStateOfCharge[g ∈ G_ess, t ∈ T], 
        SOC[g,t] ≤ storage_hrs*capacity(g)
    )
    
    # SOC in the next time is a function of SOC in the pervious time
    # with circular wrapping for the first and last t ∈ P_i
    @constraint(CATS_Model, cStateOfCharge[g ∈ G_ess, t ∈ T],
        SOC[g,t] == SOC[g,prev(t)] + CHARGE[g,t]*η_charge - GEN[g,t]/η_charge
    )
    println("Storage constraints okay.")
    ########################
    ######## DC OPF ########
    ########################
    # Create slack bus with theta=0
    fix.(THETA[slack_bus, T], 0)
    
    # Max line flow must be less than the nominal (RATE A) of the line
    @constraint(CATS_Model, cLineLimits[(i,j) ∈ L, t ∈ T], 
        FLOW[(i,j),t] ≤ line(i,j,:rate_a)*status(i,j,t)) 
    
    # Angle limited to less than 60 degrees 
    #@constraint(CATS_Model, cAngleLimitsMax[(i,j) ∈ L, t ∈ T], 
    #    (THETA[i,t] - THETA[j,t]) ≤  θlim
    #)
    #@constraint(CATS_Model, cAngleLimitsMin[(i,j) ∈ L, t ∈ T], 
    #    (THETA[i,t] - THETA[j,t]) ≥ -θlim
    #)
                    
    # Flow is governed by angle difference between buses
    @constraint(CATS_Model, cLineFlows[(i,j) ∈ L, t ∈ T],
        FLOW[(i,j),t] == line(i,j,:sus)*(THETA[i,t] - THETA[j,t])
    )

    # Power must be balanced at all nodes
    # Σ(generation) + shedding - Σ(demand) - Σ charging = Σ(flows) ∀ n ∈ N
    @constraint(CATS_Model, cBalance[i ∈ N, t ∈ T], 
        sum(GEN[g,t] for g ∈ sel(G, i))
        + SHED[i,t] - loads[i,t] 
        - sum(CHARGE[g,t] for g ∈ sel(G_ess, i))
         == sum(FLOW[(i,j),t] for j ∈ J(i))
    )
    println("Power flow constraints okay.")
    #########################
    ####### OBJECTIVE #######
    #########################

    # The weighted operational costs of running each generator
    @expression(CATS_Model, eVariableCosts,
        sum(W[t] * gens[g,:c1] * GEN[g,t] for g ∈ G, t ∈ T))
    
    # The weighted operational costs of shedding load/non-served energy (NSE)
    @expression(CATS_Model, eNSECosts,
        sum(W[t] * shed_cost * SHED[i,t] for i ∈ N, t ∈ T))

    # Fixed costs of all solar investments
	@expression(CATS_Model, eFixedCostsSolar,
        sum(solar_cost * CAP[g] for g ∈ intersect(G_new, G_solar)))

    # Fixed costs of all battery/ESS investments
    @expression(CATS_Model, eFixedCostsStorage,
		sum(battery_cost * CAP[g] for g ∈ intersect(G_new, G_ess)))

    # Minimize the sum of investment and O&M costs 
	@expression(CATS_Model, eTotalCosts,
		eVariableCosts + eNSECosts + eFixedCostsStorage + eFixedCostsSolar)

    @constraint(CATS_Model, cBudget,
        eFixedCostsStorage + eFixedCostsSolar ≤ budget
    )
    
	@objective(CATS_Model, Min, eTotalCosts)
    println("Model setup done! Starting optimization...")
    sleep(0.5) # Sleep so final print statements appear to user
    
    optimize!(CATS_Model)

    return CATS_Model
end